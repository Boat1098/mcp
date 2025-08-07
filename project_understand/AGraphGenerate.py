import os
import networkx as nx
import json
import re
from .ModuleChat import GRAPH_PROMPT, chat, SUBGRAPH_PROMPT
from .util import *
from .dataProcess import *

def extract_json_block(text):
    """
    提取文本中的第一个 JSON 代码块内容。
    :param text: 输入文本
    :return: JSON 字符串或 None
    """
    match = re.search(r'```json\n(.*?)\n```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

def extract_plantuml_block(text):
    """
    提取文本中的第一个 PlantUML 代码块内容。
    :param text: 输入文本
    :return: PlantUML 字符串或 None
    """
    match = re.search(r'```plantuml\n(.*?)\n```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None

def parse_module_groups(json_str):
    """
    将 JSON 字符串解析为 Python 字典。
    :param json_str: JSON 字符串
    :return: 解析后的字典数据
    """
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print("JSON 解析失败:", str(e))
        return None

def parse_llm_output(full_text):
    """
    主函数：解析完整LLM输出内容。
    :param full_text: 包含多个代码块的完整文本
    :return: 包含模块组和流程图的字典
    """
    # 提取 JSON 部分
    json_block = extract_json_block(full_text)
    module_data = parse_module_groups(json_block) if json_block else None

    # 提取 PlantUML 部分
    plantuml_block = extract_plantuml_block(full_text)

    return {
        "module_groups": module_data,
        "plantuml_diagram": plantuml_block
    }

def mergeDicts(dict1, dict2):
    merged = defaultdict(int)

    for d in [dict1, dict2]:
        for key, value in d.items():
            merged[key] += value

    # 转为普通字典
    merged = dict(merged)
    return merged


def getCommGraph(baseGraph, communities):
    """
    communities: {
        'id': f"Community_{idx}",
        'nodes': comm,
        'size': len(comm),
        'funcs': [self.graph.nodes[n]['fr']['functional_summary'] for n in comm],
    }
    """
    graph = nx.DiGraph()
    node_comm = {}
    for comm in communities:
        graph.add_node(comm['id'], func=comm['func'], nodes=comm['nodes'])
        for n in comm['nodes']:
            node_comm[n] = comm['id']

    for (u, v, d) in baseGraph.edges(data=True):
        if node_comm[u] != node_comm[v]:
            graph.add_edge(node_comm[u], node_comm[v], weight=d['weight'])
    return graph

class GraphGenerater:
    def __init__(self, filepath):
        """初始化参数说明：
        - filepath: depends 解析结果路径
        """
        self.dp = DataProcess(filepath)
        self.graph = None
        self.communities = None
        self.communities_graph = None
        # self.output_file = output_file
    
    def _dp_init(self):
        # p = Path(self.dp.filepath)
        # targetPath = p.with_name("save.json")
        # project_name = Path(self.dp.filepath)
        # if os.path.exists(targetPath):

        #     self.dp.load_as_json(targetPath)
        # else:
        self.dp.ModuleScores()
        self.dp.FuncScores()
        # print("start to cluster...")
        self.dp.communities_cluster()
        self.dp.communities_info()
            # self.dp.save_as_json(targetPath)
        self.communities = self.dp.communities_result
        self.graph = self.dp.graph
        self.communities_graph = None
        self._build_Community_Graph()

    def _build_Community_Graph(self):
        base_graph = self.graph.copy()
        Graph = nx.DiGraph()
        node_map = {}
        for comm in self.communities:
            Graph.add_node(comm['id'], size=comm['size'], nodes=comm['nodes'], description=comm['description'])
            for n in comm['nodes']:
                node_map[n] = comm['id']
        
        for (u, v, d) in base_graph.edges(data=True):
            if node_map[u] != node_map[v]:
                if Graph.has_edge(node_map[u], node_map[v]):
                    Graph[node_map[u]][node_map[v]]['types'] = mergeDicts(Graph[node_map[u]][node_map[v]]['types'], d['types'])
                    Graph[node_map[u]][node_map[v]]['weight'] += d['weight']
                else:
                    Graph.add_edge(node_map[u], node_map[v], types=d['types'], weight=d['weight'])
        
        self.communities_graph = Graph

    def _build_prompt(self):
        community_prompt = []
        for n in self.communities_graph.nodes():
            description = self.communities_graph.nodes[n]["description"]
            community_prompt.append({
                "id": n,
                **description
            })
        edges = [{
            "source": u,
            "target": v,
            "type": d['types'],
            "weight": d['weight']
        } for (u, v, d) in self.communities_graph.edges(data=True)]
        print(f"communities: {len(community_prompt)} edges: {len(edges)}")
        data = {
            "communities": json.dumps(community_prompt),
            "edges": json.dumps(edges),
        }
        
        prompt = GRAPH_PROMPT.format(background=BACKGRAOUND, **data)
            
        return prompt
        # return response.choices[0].text
    
    def generate_graph(self, graph: nx.DiGraph, module_name):
        community_prompt = []
        for n in graph.nodes():
            description = self.communities_graph.nodes[n]["description"]
            community_prompt.append({
                "id": n,
                **description
            })
        edges = [{
            "source": u,
            "target": v,
            "type": d['types'],
            "weight": d['weight']
        } for (u, v, d) in graph.edges(data=True)]
        edges = sorted(edges, key=lambda x: x['weight'], reverse=True)
        print(f"communities: {len(community_prompt)} edges: {len(edges)}")
        data = {
            "communities": json.dumps(community_prompt),
            "edges": json.dumps(edges[0:min(200, len(edges))]),
        }
        prompt = SUBGRAPH_PROMPT.format(background="", module_name=module_name, **data)
        result = chat(prompt)
        plantuml_block = extract_plantuml_block(result)
        return plantuml_block
    
    def optimize_by_llm(self):
        prompt = self._build_prompt()
        # print(prompt)
        result = chat(prompt)
        # print(result)
        return parse_llm_output(result)
        # return result
    
    # def save_result(self, result, targetPath):
    #     communities = result['module_groups']['module_groups']
    #     communities_map = {}
    #     architecture = []
    #     for c in self.communities:
    #         communities_map[c['id']] = c['nodes']
    #     for c in communities:
    #         comm = c['communities']
    #         nodes = []
    #         for i in comm:
    #             if i in communities_map.keys():
    #                 nodes.extend([self.graph.nodes[n]['name'] for n in communities_map[i]])
    #         architecture.append({
    #             "module_name": c['module_name'],
    #             "nodes": nodes,
    #             "reasoning": c['reasoning']
    #         })
    #     with open(os.path.join(targetPath, "architecture.json"), "w", encoding="utf-8") as f:
    #         json.dump(architecture, f, ensure_ascii=False, indent=2)
    #         f.close()

    #     with open(os.path.join(targetPath, "activity_graph.puml"), "w", encoding="utf-8") as f:
    #         f.write(result['plantuml_diagram'])
    #         f.close()

    #     with open(os.path.join(targetPath, "result.json"), "w", encoding="utf-8") as f:
    #         json.dump(result, f, ensure_ascii=False, indent=2)
    #         f.close()

    def output_result(self, result):
        communities = result['module_groups']['module_groups']
        communities_map = {}
        architecture = []
        for c in self.communities:
            communities_map[c['id']] = c['nodes']
        for c in communities:
            comm = c['communities']
            nodes = []
            for i in comm:
                if i in communities_map.keys():
                    nodes.extend([self.graph.nodes[n]['name'] for n in communities_map[i]])
            architecture.append({
                "module_name": c['module_name'],
                "nodes": nodes,
                "reasoning": c['reasoning']
            })
        return {
            'architecture': architecture,
            'plantuml_diagram': result['plantuml_diagram'],
            'communities': self.communities
        }
    
    def output(self):
        result = self.optimize_by_llm()
        communities = result['module_groups']['module_groups']
        # communities_map = {}
        # for c in communities:
        #     for i in c['communities']:
        #         communities_map[i] = c['module_name']
        # for c in arc:
        #     c['module'] = communities_map[c['id']]

        # os.makedirs(os.path.join(targetPath, "graph"), exist_ok=True)
        pumls = []
        for c in communities:
            module_name = c['module_name']
            # str.replace()
            module_name = module_name.replace("/", "_")
            module_name = module_name.replace("\\", "_")
            nodes = c['communities']
            sub_graph = self.communities_graph.subgraph(nodes)
            puml = self.generate_graph(sub_graph, module_name=module_name)
            pumls.append({
                'module_name': module_name,
                'content': puml
            })
        
        return {
            # 'architecture': architecture,
            'plantuml_diagram': result['plantuml_diagram'],
            'communities': self.communities,
            'nodes': [{
                "id": n,
                "name": self.graph.nodes[n]['name'],
                "fr": self.graph.nodes[n]['fr'],
            } for n in self.graph.nodes()],
            'sub_pumls': pumls,
        }


if __name__ == "__main__":

    
    filepath = "./data/data/bash/bash_gt-file.json"
    # filepath = "./data/data/distributed_camera/distributed_camera-file.json"
    ag = GraphGenerater(filepath)
    res = ag.optimize_by_llm()
    # ag.save_result(res, "./data/data/distributed_camera")
    # ag.save_result(res, "./data/data/bash")

        