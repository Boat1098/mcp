from typing import List, Dict, Union, Callable
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from concurrent.futures import ThreadPoolExecutor, as_completed

Config = {
    "key": "sk-e47c9bef984c45b18db55d980dfd70fc",
    "model": "deepseek-chat",
    "http": "https://api.deepseek.com"
}

TypeWeight = {
    "Implement": 7.575,
    "Throw": 9.053,
    "Call": 0.177,
    "Create": 1.665,
    "ImplLink": 9.33,
    "Extend": 2.159,
    "Use": 0.509,
    "Parameter": 5.146,
    "Import": 8.300,
    "Cast": 0.701,
    "Return": 5.702,
    "Contain": 4.478
}

BACKGRAOUND = """
"""

FILE_PROMPT = """
**Role: * * You are an experienced software engineer/system analyst, skilled in understanding code structure and project architecture.
**Task: * * Please conduct a thorough analysis of the provided project background information and the content fragments of the target file.
**Output requirements:**
1. Strictly use JSON format output, including the following fields, but do not add any modifiers:
{{
    "functional_relevance": {{
        "score": "a numerical value between 0-1",
        "reason": "Rating criteria within 20 words "
    }},
    "criticality": {{
        "score": "a numerical value between 0-1",
        "reason": "Rating criteria within 20 words "
    }},
    "functional_summary": " Function description within 50 words",
    "dependencies": ["Key modules/files that this file depends on "],
    "dependent_modules": ["Key modules/files that depend on this file "],
    "analysis_insights": ["Content based 2-3 key findings"]
}}  
2. Rating criteria:
Functionalized relevance score: The correlation between the file and the core functionality of the project (0=irrelevant, 1=core)
Criticality. score: The irreplaceability of a file in a project (0=deletable, 1=irreplaceable)

**The information provided to you:**
*Overall Background and Function of the Project:**
    {background}
** * Target File Content:**
    {file_content}

**Please begin your analysis:**
"""

COMMUNITY_PROMPT = """
**Role: * * You are an experienced software engineer/system analyst, skilled in understanding code structure and project architecture.
**Task: * * There is a community consisting of some code files. Please conduct high-level functional analysis and architecture evaluation of the community based on the overall project background information and relevant information provided.
**Output requirements:**
1. Strictly use JSON format output, including the following fields, but do not add any modifiers:
{{
    "community_summary": "Overall functional description of the community (within 60 words)",
    "architectural_role": [" Core Services "," Support Modules "," Data Hubs "]//Multiple choice tags
    "project_alignment": {{
        "score": 0-1, //Consistency with project objectives
        "reason": "Basis within 20 words"
    }},
    "key_functions": [" Function Point 1 "," Function Point 2 "," Function Point 3 "],
    "cross_community_impact": {{
        "provides": ["services provided to other communities"],
        "requires": ["Dependent external capabilities"]
    }},
}}  

Analysis rules:
1. The community summary needs to integrate all file functions and highlight common goals=
2. Choose architecture roles with no more than 3 most matching labels
3. Cross community impact analysis based on dependency relationship data
4. Improvement suggestions need to consider the importance rating of documents

**The information provided to you:**
*Overall Background and Function of the Project:**
    {background}
*Community Content:**
    {community_content}
**Please begin your analysis:**
"""

GRAPH_PROMPT = """
You are an experienced software system analyst, skilled in recovering the architecture and module organization of software systems from dependency graphs and module clustering.
Please complete two subtasks based on the following information and return structured results separately:
---
## Input data
- **Project functional background (background)**:
{background}
- ** Community clustering information  (community_content)**:
{communities}
- **Dependency graph relationship (edges_info)**:
{edges}
---

##Task 1: Suggestions for functional module division
Please reasonably infer which functional modules/subsystems the community should belong to based on its functions, dependencies, and module collaboration. We hope to output the results from the perspective of "folder partitioning", that is, which files in the community should be placed in the same subdirectories to form independent functional modules or subsystems.
**The output format is as follows (JSON):**
```json
{{
  "module_groups": [
    {{
      "module_name": "Module/folder name ",
      "communities": ["C1", "C5", "C7"],
      "reasoning": "These communities are jointly responsible for XXX functionality and have close dependencies"
    }}
  ]
}}
```

Please note that due to functional requirements, please do not miss any of them
---
##Task 2: Generation of module level function flow chart
Please generate a high-level functional flowchart based on the functionality of modules/subsystems and the dependencies between communities. A flowchart is used to display the control flow or data flow between modules, clearly describing the functional execution path of the system.
-Only focus on the call paths and dependency order between modules.
-Each module is a logical node, indicating its functional summary.
-Highlight core modules, fade peripheral modules, and bold critical paths.
**Output format suggestion (PlantUML format structured output):**

```plantuml
@startuml
title <System Name> Module level Function Flow Chart

skinparam nodesep 30
skinparam ranksep 40

package "Module A Name" {{
  rectangle "Function A Summary \ \ n Includes: C1, C2" as A # Red
}}

package "Module B Name" {{
  rectangle "Function B Summary \ \ n Includes: C3" as B # Red
}}


A --> B : Control flow call

@enduml
```
---
## 🔁 Summary of Output Format Requirements
---
Please strictly divide the final output into two parts and mark them with the following structure:

###Module division results###
<Please use JSON structure to output module partitioning suggestions>

###Functional flowchart###
Please output the flowchart using PlantUML syntax

Please do not omit any item. Avoid outputting irrelevant content except for necessary annotations.
"""

SUBGRAPH_PROMPT = """
You are an experienced software system analyst, skilled in recovering the architecture and module organization of software systems from dependency graphs and module clustering.
Please complete the task based on the following information:
---
## Input data
- **Project functional background (background)**:
{background}
- **Module name (The modules to which these communities belong)**:
{module_name}
- ** Community clustering information  (community_content)**:
{communities}
- **Dependency graph relationship (edges_info)**:
{edges}
---
## Task:
Please generate a high-level functional flowchart based on the functionality of modules/subsystems and the dependencies between communities. A flowchart is used to display the control flow or data flow between modules, clearly describing the functional execution path of the system.
-Only focus on the call paths and dependency order between modules.
-Each module is a logical node, indicating its functional summary.
-Highlight core modules, fade peripheral modules, and bold critical paths.
**Output format suggestion (PlantUML format structured output):**

```plantuml
@startuml
title <System Name> Communities level Function Flow Chart

skinparam nodesep 30
skinparam ranksep 40

package "Module A Name" {{
  rectangle "Function A Summary \ \ n Includes: C1, C2" as A # Red
}}

package "Module B Name" {{
  rectangle "Function B Summary \ \ n Includes: C3" as B # Red
}}


A --> B : Control flow call

@enduml
```

Additionally, due to the requirements of the rules, do not omit any of them.Avoid outputting irrelevant content except for necessary annotations.
"""

# 同步 OpenAI 客户端初始化
client = OpenAI(
    api_key=Config.get("key"),
    base_url=Config.get("http")
)

def batch_chat_requests(
    data_list: List[Dict],
    render_prompt_fn: Callable[[Dict], str],
    model: str = None,
    max_concurrent_requests: int = 8,
) -> List[Union[str, Exception]]:
    if model is None:
        model = Config.get("model")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def call_openai(prompt: str) -> str:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                timeout=30,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error: {e}")
            raise

    prompts = [render_prompt_fn(data) for data in data_list]
    results = []

    with ThreadPoolExecutor(max_workers=max_concurrent_requests) as executor:
        future_to_prompt = {executor.submit(call_openai, prompt): prompt for prompt in prompts}
        for future in as_completed(future_to_prompt):
            try:
                result = future.result()
            except Exception as exc:
                result = exc
            results.append(result)

    return results

def chat(prompt: str) -> str:
    response = client.chat.completions.create(
        model=Config.get("model"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()