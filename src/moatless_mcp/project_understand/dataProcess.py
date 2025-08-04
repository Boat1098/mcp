import os
import json
import xml.etree.ElementTree as ET
# from util import *
from .ModuleChat import BACKGRAOUND, COMMUNITY_PROMPT, batch_chat_requests, FILE_PROMPT, TypeWeight
# from openai import OpenAI
import json
from networkx.readwrite import json_graph
from pathlib import Path
import networkx as nx
from .util import cluster_by_leiden
from moatless_mcp.utils.config import Config
import logging

# config = Config.from_env()
# TypeWeight = config.TypeWeight

logger = logging.getLogger(__name__)
# file_handler = logging.FileHandler('D:/Files/mcp/understand_dataProcess.log')
# file_handler.setLevel(logging.DEBUG)  # 设置文件日志级别

# # 定义日志输出格式
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# file_handler.setFormatter(formatter)

# # 将 FileHandler 添加到 logger
# logger.addHandler(file_handler)

def getFileDependices(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
        return None

    with open(filepath, encoding='utf-8') as f:
        data = json.load(f)
        f.close()

    return data

def getFileContent(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
        return None

    with open(filepath, encoding='utf-8') as f:
        content = f.read()
        f.close()

    return content

def type_check(tar):
    if "possible" in tar:
        key = tar.split("(")[0]
    else:
        key = tar
    return TypeWeight.get(key, 0)
# def type_check()

def tokenize_path(path: str):
    """将路径按目录拆分成token"""
    return path.strip(os.sep).split(os.sep)

def jaccard_similarity(tokens1, tokens2):
    """计算路径token的Jaccard相似度"""
    set1, set2 = set(tokens1), set(tokens2)
    if not set1 or not set2:
        return 0.0
    return len(set1 & set2) / len(set1 | set2)

def get_new_graph(target_graph, communities):
    """
    communities: {
        id: str,
        nodes: list[int]
    }
    """
    graph = nx.DiGraph()
    node_comm = {}
    for comm in communities:
        graph.add_node(comm['id'], nodes=comm['nodes'])
        for n in comm['nodes']:
            node_comm[n] = comm['id']

    for (u, v, d) in target_graph.edges(data=True):
        if node_comm[u] != node_comm[v]:
            graph.add_edge(node_comm[u], node_comm[v], weight=d['weight'])
    return graph

class DataProcess:
    def __init__(self, filepath):
        self.filepath = filepath
        self.filecontent = getFileDependices(filepath)
        self.dependencies = self.filecontent["cells"]
        self.files = self.filecontent["variables"]
        self.graph = self._build_graph()
        self.communities_result = []
    
    # def build_self()
    def _build_graph(self):
        G = nx.DiGraph()
        for index, cell in enumerate(self.files):
            path = Path(cell)
            filename = cell
            content = getFileContent(path)
            # if content == "":
            #     continue
            G.add_node(index, name=filename, content=content)
        for cell in self.dependencies:
            src = cell["src"]
            dest = cell["dest"]
            weight = 0
            for key, value in cell['values'].items():
                weight += type_check(key) * value
            
            G.add_edge(src, dest, weight=weight, types=cell['values'])
        return G

    def ModuleScores(self):
        graph = self.graph.reverse()
        ipr_scores = nx.pagerank(graph, alpha=0.85, max_iter=100)
        for n in self.graph.nodes():
            self.graph.nodes[n]['score'] = ipr_scores.get(n, 0.5)
    
    def FuncScores(self):
        import random
        logger.info("start of func scores")
        #todo：这里需要实现拓扑调用的LLM请求，需要重新考虑Prompt要用那些信息（目前只用了文件的内容，拓扑的信息也并未使用）
        file_graph = self.graph.copy()
        ids = [i for i in self.graph.nodes()]
        prompt_data = []
        def getPrompt(data):
            return FILE_PROMPT.format(background=data['background'], file_content=data['file_content'])
        
        # 检查是否是有向无环图
        if nx.is_directed_acyclic_graph(file_graph):
            # 拓扑排序
            order = list(nx.topological_sort(file_graph))
            print("Topological order:", order)

        else:
            print("Graph contains cycles, topological sort not applicable.")
            target_graph = file_graph.reverse()
            source_nodes = [n for n, d in target_graph.in_degree() if d == 0]
            print("Source nodes:", source_nodes)
            # 从这些源点出发做 BFS 或 DFS
            queue = list(source_nodes)
            visited = set(queue)
            order = []
            while True:
                while queue:
                    current = queue.pop(0)
                    order.append(current)
                    # print(f"Processing source-dependent node {current}")

                    # print(res)
                    # target_graph.nodes[current]["fr"] = res
                    for neighbor in target_graph.successors(current):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                remains = [i for i in ids if i not in visited]
                if len(remains) == 0:
                    break
                queue.append(random.choice(remains))
        
        for o in order:
            content = self.graph.nodes[o]['content'].split("\n")
            if len(content) > 5000:
                content = content[0:5000]
            prompt_data.append({
                "id": o,
                "background": BACKGRAOUND,
                "file_content": "\n".join(content)
            })
        # self.graphes.append(target_graph.reverse())
        result = batch_chat_requests(prompt_data, getPrompt)
        for idx, res in enumerate(result):
            node = prompt_data[idx]['id']
            if isinstance(res, Exception):
                continue
            res = res.replace('```json', '')
            res = res.replace('```', '')
            self.graph.nodes[node]["fr"] = json.loads(res)
        logger.info("end of func scores")

        for n in self.graph.nodes():
            if self.graph.nodes[n].get("fr", None) is None:
                name = self.graph.nodes[n]['name']
                logger.info(f"{name} has no fr")
    
    def save_as_json(self, output_path):
        # self.filepath = filepath
        # self.filecontent = getFileDependices(filepath)
        # self.dependencies = self.filecontent["cells"]
        # self.files = self.filecontent["variables"]
        # self.graph = self._build_graph()
        # self.communities_result = []
        data = json_graph.node_link_data(self.graph)
        tar = {
            "filepath": self.filepath,
            "graph": data,
            "communities": self.communities_result
        }
        with open(output_path, "w", encoding='utf-8') as f:
            json.dump(tar, f, indent=4, ensure_ascii=False)
            f.close
        return

    def load_as_json(self, input_path):
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            f.close()
        target_graph = json_graph.node_link_graph(data['graph'])
        for (u, v, d) in target_graph.edges(data=True):
            self.graph.add_edge(u, v, **d)

        self.communities_result = data['communities']

    def cluster_core(self, target_graph):
        # todo: 关于多次迭代的问题，目前考虑在限制20的情况下，需要限制comm的数量，进而需要重复的聚类，实现思路方面，维护一个社区列表，不断更新graph，每次聚类后，更新社区列表
        # todo：关于社区的信息，也需要通过LLM获取结构化信息（这部分Prompt还未完成，需要考虑要使用那些信息）
        communities = cluster_by_leiden(target_graph, resolution=0.5, max_comm_size=10, weight='weight')
        comm_dict = {}
        for node, label in zip(target_graph, communities):
            comm_dict.setdefault(label, []).append(node)
        return comm_dict
    
    def communities_cluster(self):
        logger.info("start of communities cluster")
        BATCH = 200
        cluster_result = []
        # node_comm_map = {}
        comm_dict = {}
        # for n in self.graph.nodes():
        #     node_comm_map[n] = None
        base_graph = self.graph.copy()
        for (u, v, d) in base_graph.edges(data=True):
            weight = base_graph[u][v]['weight']
            w_u = base_graph.nodes[u]['score']
            r_u = base_graph.nodes[u]['fr']['functional_relevance']['score']
            w_v = base_graph.nodes[v]['score']
            r_v = base_graph.nodes[v]['fr']['functional_relevance']['score']
            if float(r_v) == 0:
                base_graph[u][v]['weight'] = (w_u + w_v) * (float(r_u)) * weight
            else:
                base_graph[u][v]['weight'] = (w_u + w_v) * (float(r_u) / float(r_v)) * weight

        # target_graph = base_graph.copy()
        isloated_nodes = list(nx.isolates(base_graph))
        
        target_graph = base_graph.copy()
        # base_graph.
        target_graph.remove_nodes_from(isloated_nodes)
        while True:
            if len(comm_dict.keys()) == 0:
                comm_dict = self.cluster_core(target_graph)
                if len(comm_dict.keys()) < BATCH:
                    break
            else:
                target_graph = get_new_graph(base_graph, [{
                    "id": label,
                    "nodes": value
                } for label, value in comm_dict.items()])
                new_comm_dict = self.cluster_core(target_graph)
                for k, v in new_comm_dict.items():
                    tar = []
                    for b in v:
                        tar.extend(comm_dict[b])
                    new_comm_dict[k] = tar
                comm_dict = new_comm_dict
                if len(comm_dict.keys()) < BATCH:
                    break
        
        communities = sorted(comm_dict.values(), key=len, reverse=True)
        communities = self.IsolatedNodeCluster(isloated_nodes, communities)
        # print(len(communities))
        communities_result = []
        count = 0
        for idx, comm in enumerate(communities):
            if len(comm) == 1:
                count += 1
            communities_result.append({
                'id': f"Community_{idx}",
                'nodes': comm,
                'size': len(comm),
                'funcs': [self.graph.nodes[n]['fr']['functional_summary'] for n in comm],
            })
        print(count)
        self.communities_result = communities_result
        logger.info("end of func communities cluster")
        return communities_result

    def PathSimilarity(self, node, community):
        """node: id, community: list(id)"""
        path = self.graph.nodes[node]['name']
        scores = []
        for id in community:
            tar_path = self.graph.nodes[id]['name']
            score = jaccard_similarity(tokenize_path(path), tokenize_path(tar_path))
            scores.append(score)
        return sum(scores) / len(scores) if scores else 0.0


    def IsolatedNodeCluster(self, isolated_nodes, communities, threshold=0.5):
        def best_community_get(node, communities):
            best_score = 0
            best_community = None
            for id, comm in enumerate(communities):
                score = self.PathSimilarity(node, comm)
                print(f"Similarity with {id}: {score:.3f}")
                if score > best_score:
                    best_score = score
                    best_community = comm
            if best_score >= threshold:
                return best_community, best_score
            else:
                return None, best_score
        for node in isolated_nodes:
            bc, bs = best_community_get(node, communities)
            if bc == None:
                communities.append([node])
            else:
                bc.append(node)
        return sorted(communities, key=len, reverse=True)
    
    def communities_info(self):
        def prompt_get(data):
            return COMMUNITY_PROMPT.format(background=data['background'], community_content=data['community_content'])

        prompt_data = []
        for c in self.communities_result:
            comm = []
            for n in c['nodes']:
                comm.append({
                    "path": self.graph.nodes[n]['name'],
                    "functional_summary": self.graph.nodes[n]['fr']['functional_summary'],
                    "criticality": self.graph.nodes[n]['fr']['criticality']['score'],
                })
            prompt_data.append({
                "background": BACKGRAOUND,
                "community_content": json.dumps({
                    "id": c['id'],
                    "size": c['size'],
                    "files": comm
                }),
                # "render_prompt_fn": prompt_get
            })

        result = batch_chat_requests(prompt_data, render_prompt_fn=prompt_get)
        for idx, res in enumerate(result):
            if isinstance(res, Exception):
                continue
            res = res.replace('```json', '')
            res = res.replace('```', '')
            # self.graph.nodes[node]["fr"] = json.loads(res)
            self.communities_result[idx]['description'] = json.loads(res)
        return result


if __name__ == "__main__":
    # with open("./data/data/bash/bash_relations.json", "r") as f:
    #     data = json.load(f)
    #     f.close()
    # graph = json_graph.node_link_graph(data)
    # for n in graph.nodes():
    #     name = graph.nodes[n]['name']
    #     name = name.replace("\\", "/")
    #     # str.replace()
    #     graph.nodes[n]['name'] = str(Path(name))
        
    # with open("./data/data/bash/bash_relations.json", "w") as f:
    #     data = json_graph.node_link_data(graph)
    #     json.dump(data, f, ensure_ascii=False, indent=4)
    #     f.close()
    
    filepath = "./data/data/bash/bash_gt-file.json"
    dp = DataProcess(filepath)
    
    dp.ModuleScores()
    dp.FuncScores()
    dp.communities_cluster()
    dp.communities_info()
    dp.save_as_json("./data/data/bash/bash_dataProcess.json")


