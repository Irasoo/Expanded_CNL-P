# Expanded CNL-P

---

## Project Structure

### About `cnlp_linting_tool`

The `common` directory contains general-purpose methods for processing results.  
The `llm` directory contains the LLM client classes and related methods.  
The `parser_like` directory contains the updated CNL-P Parser_Like.  
The `schemas` directory contains type definitions used for data exchange during static analysis.  
The `config.py` file contains the configuration for the linting tool, where you can define which modules to check and modify necessary fields in `AST_Like`.  
To view the contents of `NodeVisitor_Like`, please refer to [CNL-P](https://github.com/Irasoo/CNL-P).

```
cnlp_linting_tool/
├── common/                    # Common utility methods
├── llm/                       # LLM client classes and related methods
├── parser_like/               # Updated CNL-P Parser_Like implementation
├── schemas/                   # Type definitions for static analysis
├── config.py                  # Linting tool configuration
```

### About `experiments`
This directory contains three main research questions (`RQ1`, `RQ2`, `RQ3`) and their corresponding experimental setups, results, and tools.
```
experiments/
├── RQ1/
│   ├── user_study_result/                 # Prompts, rating sheets, and feedback from participants
│   ├── CNL-P_prompt_writing_tutorial.md   # Learning material for participants
│   └── summary_rq1_result.py              # Script for summarizing and plotting RQ1 results
│
├── RQ2/
│   ├── linting_agent_based_on_llms/       # Baseline LLM-based linting agent for static checking
│   ├── result/                            # Experimental results for RQ2
│   ├── task/                              # Custom datasets containing CNL-P syntax errors
│   └── main.py                            # Script to run RQ2 experiments
│
└── RQ3/
├── result/                            # Results using the extended CNL-P syntax
├── saved_instances/                   # Experiment instances selected using random seeds
├── task_definition/                   # Prompts converted from NL to CNL-P/RISEN/RODES
├── main.py                            # Script to run RQ3 experiments
└── tools.py                           # Utility functions (dataset loading, prompt conversion, etc.)
```

---

## Prerequisites
1. **Specify the Python version as Python 3.11.8**
2. **Install dependencies**
```bash
pip install -r requirements.txt
````

3. **Create a `.env` file**
   In the root directory of the project, create a `.env` file with the following content:<br>
   OPENAI_API_KEY=your_key<br>
   OPENAI_MODEL="gpt-4.1"<br>
   BASE_URL="[https://api.rcouyi.com/v1](https://api.rcouyi.com/v1)"

4. **Download the dataset**
   Download the [natural-instructions dataset](https://github.com/allenai/natural-instructions) and extract it into the root directory of the project.

---

## Running the Experiments

### Running RQ1

```bash
cd ./experiments/RQ1
python summary_rq1_result.py
```

### Running RQ2

```bash
cd ./experiments/RQ2
python main.py
```

### Running RQ3

```bash
cd ./experiments/RQ3
python main.py
```

