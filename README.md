# Expanded CNL-P

## Project Structure

| Directory | Contents |
| --- | --- |
| [src/cnlp_compiler/](src/cnlp_compiler/) | CNL-P parsing, static checking, control-flow processing, and Agent code generation. |
| [src/converter/](src/converter/) | A converter and model request client for converting natural-language instructions into CNL-P, RISEN, or RODES. |
| [experiments/RQ2/](experiments/RQ2/) | Experiments on model understanding and execution of CNL-P, RISEN, RODES, and natural-language instructions. |
| [experiments/RQ3/](experiments/RQ3/) | Experiments on static checking of CNL-P syntax and semantic errors. |
| [experiments/RQ4/](experiments/RQ4/) | Experiments on Agent code generation and execution. |
| [experiment_results/RQ1/](experiment_results/RQ1/) | Participant programs, scores, and feedback from the user study. |
| [experiment_results/RQ2/](experiment_results/RQ2/) | Task instances, instructions used in the experiments, human ratings, model responses, and accuracy results. |
| [experiment_results/RQ3/](experiment_results/RQ3/) | Outputs and records from the static-checking experiments. |
| [experiment_results/RQ4/](experiment_results/RQ4/) | Generated Agent programs, execution outputs, and evaluation records. |

## Environment Setup

### 1. Python Version

Use **Python 3.11.8**.


### 2. Install Dependencies

Run the following command from the repository root, which contains [requirements.txt](requirements.txt):


```powershell
python -m pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy [.env.example](.env.example) in the repository root to `.env` in the same directory, then enter your configuration. If `.env` already exists, edit that file directly.


```powershell
if (-not (Test-Path -LiteralPath ".env")) { Copy-Item -LiteralPath ".env.example" -Destination ".env" }
```

The basic configuration is shown below. Replace the example endpoint, API key, and model name with your actual values:


```dotenv
BASE_URL=https://your-provider.example/v1
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=your-model-id
```

| Variable | Purpose |
| --- | --- |
| [BASE_URL](src/converter/client.py) | The model service endpoint. |
| [OPENAI_API_KEY](src/converter/client.py) | The model service API key shared by the compiler, converter, and experiment code; configure it once. |
| [OPENAI_MODEL](src/cnlp_compiler/utils/llm.py) | The default model name used by the compiler. |
| [OPENAI_ORG](src/cnlp_compiler/utils/llm.py) | An optional organization identifier; omit it if the service does not require it. |

Both the compiler and converter read [OPENAI_API_KEY](src/converter/client.py). The compiler's default model is specified by [OPENAI_MODEL](src/cnlp_compiler/utils/llm.py), while the converter's model name is supplied as a call argument.


### 4. Data Locations

The repository includes the task instances used in RQ2:


- [instances/natural_instructions/](experiment_results/RQ2/instances/natural_instructions/): Instances from six Natural Instructions tasks.
- [instances/kor_bench/](experiment_results/RQ2/instances/kor_bench/): Ten KOR-Bench rule instances.

The paths for both datasets are configured under `paths.instances` in [experiments/RQ2/config.yaml](experiments/RQ2/config.yaml).


RQ3 error instances are stored in [semantic/tasks/](experiments/RQ3/semantic/tasks/) and [syntaxical/task/](experiments/RQ3/syntaxical/task/). RQ4 specifications and test inputs are stored in [cases/](experiments/RQ4/cases/).


## Running the Experiments

Run the following commands from the repository root.


### RQ2

```powershell
python experiments/RQ2/main.py
```

### RQ3

#### Error-Checking Experiments

```powershell
python src/cnlp_compiler/run_linting.py
```

#### Validation of Error-Free Templates

```powershell
python src/cnlp_compiler/validate_templates.py
```

### RQ4

```powershell
python experiments/RQ4/main.py
```

By default, the entry point runs five combinations across four cases: Generator (Native), Generator (LangGraph), and Codex with CNL-P, plus Codex with NL and Codex with RISEN. Each of the three CNL-P combinations performs 5 independent generations; NL performs 4, and RISEN performs 3. Each test scenario is executed 3 times.


Generation is serial. The maximum numbers of concurrent executions for CNL-P, NL, and RISEN are 1, 3, and 4, respectively. Execution mode, experiment scope, and repetition counts are configured at the top of [experiments/RQ4/main.py](experiments/RQ4/main.py).

---

## 项目结构

| 目录 | 内容 |
| --- | --- |
| [src/cnlp_compiler/](src/cnlp_compiler/) | CNL-P 解析、静态检查、控制流程处理及 Agent 代码生成。 |
| [src/converter/](src/converter/) | 将自然语言指令转换为 CNL-P、RISEN 或 RODES 的转换器及模型请求客户端。 |
| [experiments/RQ2/](experiments/RQ2/) | 模型对 CNL-P、RISEN、RODES 与自然语言指令的理解和执行实验。 |
| [experiments/RQ3/](experiments/RQ3/) | CNL-P 语法错误和语义错误的静态检查实验。 |
| [experiments/RQ4/](experiments/RQ4/) | Agent 代码生成与执行实验。 |
| [experiment_results/RQ1/](experiment_results/RQ1/) | 用户研究中的参与者程序、评分和反馈。 |
| [experiment_results/RQ2/](experiment_results/RQ2/) | 任务实例、实际指令、人工评分、模型回答及准确率结果。 |
| [experiment_results/RQ3/](experiment_results/RQ3/) | 静态检查实验的输出与记录。 |
| [experiment_results/RQ4/](experiment_results/RQ4/) | 生成的 Agent 程序、执行输出及评价记录。 |

## 环境准备

### 1. Python 版本


使用 **Python 3.11.8**。

### 2. 安装依赖


在仓库根目录，即包含 [requirements.txt](requirements.txt) 的目录，执行：

```powershell
python -m pip install -r requirements.txt
```

### 3. 配置环境变量


将仓库根目录的 [.env.example](.env.example) 复制为同一目录下的 `.env`，填写实际配置。已有 `.env` 时直接修改其中的配置。

```powershell
if (-not (Test-Path -LiteralPath ".env")) { Copy-Item -LiteralPath ".env.example" -Destination ".env" }
```


基本配置如下，示例中的服务地址、密钥和模型名称需要替换为实际值：

```dotenv
BASE_URL=https://your-provider.example/v1
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=your-model-id
```

| 变量 | 用途 |
| --- | --- |
| [BASE_URL](src/converter/client.py) | 模型服务的接口地址。 |
| [OPENAI_API_KEY](src/converter/client.py) | 编译器、转换器及实验代码共用的模型服务密钥，只需填写一次。 |
| [OPENAI_MODEL](src/cnlp_compiler/utils/llm.py) | 编译器使用的默认模型名称。 |
| [OPENAI_ORG](src/cnlp_compiler/utils/llm.py) | 可选的组织标识，服务不要求时无需填写。 |


编译器和转换器统一读取 [OPENAI_API_KEY](src/converter/client.py)。编译器的默认模型由 [OPENAI_MODEL](src/cnlp_compiler/utils/llm.py) 指定，转换器的模型名称由调用参数指定。

### 4. 数据位置


仓库已包含 RQ2 使用的任务实例：

- [instances/natural_instructions/](experiment_results/RQ2/instances/natural_instructions/)：Natural Instructions 的六项任务实例。
- [instances/kor_bench/](experiment_results/RQ2/instances/kor_bench/)：KOR-Bench 的十条规则实例。


两个数据集的读取路径在 [experiments/RQ2/config.yaml](experiments/RQ2/config.yaml) 的 `paths.instances` 中配置。


RQ3 的错误实例分别保存在 [semantic/tasks/](experiments/RQ3/semantic/tasks/) 和 [syntaxical/task/](experiments/RQ3/syntaxical/task/)，RQ4 的需求文件与测试输入保存在 [cases/](experiments/RQ4/cases/)。

## 实验启动


以下命令在仓库根目录执行。

### RQ2

```powershell
python experiments/RQ2/main.py
```

### RQ3

#### 错误检查实验

```powershell
python src/cnlp_compiler/run_linting.py
```

#### 无错模板验证

```powershell
python src/cnlp_compiler/validate_templates.py
```

### RQ4

```powershell
python experiments/RQ4/main.py
```


默认执行 CNL-P 的 Generator (Native)、Generator (LangGraph)、Codex，以及 NL 的 Codex 和 RISEN 的 Codex，共五个组合，覆盖四个 Case。CNL-P 的三个组合各生成 5 次，NL 生成 4 次，RISEN 生成 3 次；每个测试场景重复运行 3 次。


生成阶段串行执行；运行阶段 CNL-P、NL、RISEN 的最大并行数分别为 1、3、4。执行模式、实验范围与次数在 [experiments/RQ4/main.py](experiments/RQ4/main.py) 顶部设置。
