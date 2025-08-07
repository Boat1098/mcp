from openai import OpenAI
from igraph import Graph
from collections import defaultdict
# from sentence_transformers import SentenceTransformer
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import pdist
import numpy as np
import leidenalg as la
import igraph as ig
import networkx as nx
import networkx.readwrite.json_graph as jg
import json
import re


# model = SentenceTransformer("./model/jina_embedding/", trust_remote_code=True)

def remove_think_tag(response):
    patten = r'<think>.*?</think>'
    return re.sub(patten, '', response, flags=re.DOTALL).strip()

def cluster_by_leiden(graph, resolution=0.5, max_comm_size=20, weight="weight"):
    target_graph = ig.Graph.from_networkx(graph)
    leiden_communities = la.find_partition(target_graph, la.RBConfigurationVertexPartition, weights=weight, resolution_parameter=resolution, max_comm_size=max_comm_size)
    communities = leiden_communities.membership
    return communities

def nx_to_json(graph, target_file):
    tx = jg.node_link_data(graph)
    with open(target_file, 'w') as f:
        json.dump(tx, f)
        f.close()
    return tx

def recover_graph_from_json(source_file):
    with open(source_file, 'r') as f:
        data = json.load(f)
        f.close()
    return jg.node_link_graph(data)


# def cluster_by_call(nodes):
#     """
#     nodes: list[{
#         name: str,
#         call_lines: str,
#     }]
#     Target: cluster nodes by call
#     """
#     def cluster_By_Call(self):
#         # 在聚类的最开始，我们选择针对功能相似但实现不同的节点进行聚类
#         # 在实现上，我们选择提取节点的调用场景，并根据向量化和向量相似度实现聚类
#         files = self.analysis_data.files
#         refs = self.analysis_data.file_refs
#         data_set = self.analysis_data.data_set
#         file_refs = {}
#         for ref in refs:
#             callee = ref['callee']['id']
#             lines = ref['lines']
#             kind = ref['kind']
#             if "Call" not in kind:
#                 continue
#             if callee not in file_refs.keys():
#                 file_refs[callee] = []
#             file_refs[callee].append("\n".join(lines))

#         # print(file_refs)
#         result = cluster_by_model(file_refs)
#         cluster_result = {}

#         for cls, label in result:
#             if label not in cluster_result.keys():
#                 cluster_result[label] = [cls]
#             else:
#                 cluster_result[label].append(cls)
#         with open("./RepoAssistant/data/logs/test_call_2.log", "w", encoding="utf-8") as f:
#             f.write(str(file_refs))
#         # cluster_result = {}
#         # for cls, label in result:
#         #     cluster_result[cls] = label
#         return cluster_result
    

# def cluster_by_model(data):
#     # 2. 对每个类中的代码字符串生成语义嵌入，并聚合（取平均）
#     class_names = list(data.keys())
#     class_embeddings = []
#     for cls in class_names:
#         code_strings = data[cls]
#         # 获取每个代码字符串的嵌入
#         embeddings = model.encode(code_strings)
#         # 对该类所有嵌入取平均，得到整体向量表示
#         avg_embedding = np.mean(embeddings, axis=0)
#         class_embeddings.append(avg_embedding)
#     class_embeddings = np.array(class_embeddings)

#     # 3. 计算所有类之间的余弦距离
#     # pdist 使用余弦距离，返回的是 1 - cosine similarity
#     pairwise_dist = pdist(class_embeddings, metric='cosine')

#     # 4. 基于平均链接法进行层次聚类
#     linkage_matrix = linkage(pairwise_dist, method='average')

#     # 5. 使用距离阈值划分簇
#     # 目标相似度为 0.8，对应距离阈值为 1 - 0.8 = 0.2
#     threshold = 0.2
#     cluster_labels = fcluster(linkage_matrix, t=threshold, criterion='distance')

#     # 输出每个类对应的簇编号
#     for cls, label in zip(class_names, cluster_labels):
#         print(f"类 {cls} 被划分到簇 {label}")

#     return zip(class_names, cluster_labels)
