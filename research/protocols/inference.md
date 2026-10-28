# Formal-88 VLM 推理协议 v1

冻结日期：2026-09-24  
状态：**Formal-88 正式推理已完成：1056/1056 唯一合法结果，无 Gold 完整性检查通过。**

## 1. 研究问题

在固定图像、固定 taxonomy 和固定输出结构下：

1. 不同 VLM 对自动生成学术海报可见缺陷的识别可靠性如何？
2. Prompt 从简短评论、显式 taxonomy 到 evidence-grounded 审计时，性能如何变化？
3. Natural-40 与 Controlled-48 上的表现是否一致？

## 2. 输入与防泄漏

- 输入只包含冻结的 2400×1350 PNG 和冻结 Prompt。
- runner 只读取 `formal88_image_manifest.json`，不读取 Gold CSV。
- 不向模型展示 sample ID、natural/controlled 身份、control/mutation 身份或 Gold。
- 每张图在各 provider 上均使用最高可行的图像细节设置；不得为某一模型单独裁图。
- 主实验只使用整图。固定六裁图仅可作为主实验完成后的预注册消融。

## 3. 标签与严重度

- 使用 taxonomy v4.2 的 9 个缺陷标签；`none` 不是缺陷标签。
- 每个标签最多出现一次。
- 1=minor，2=moderate，3=severe。
- 主分析只把 2–3 级计为阳性；1 级仅用于探索性分析。
- `primary_issue` 必须来自已记录的 2–3 级问题；若不存在则为 `none`。
- Primary 依次考虑：实际内容丢失/硬故障、严重度、信息重要性、覆盖面积。

## 4. Prompt 条件

- **P1 `paper2poster_style`**：Paper2Poster-inspired 的简短视觉评论基线。保留其
  先检查 overflow/blank area、保守报告和给出修复建议的风格，但由于官方 Commenter
  是局部 panel critic 且依赖正反例图，本实验必须扩展为整图九类输出。因此它是
  **task-adapted baseline，不是官方 Prompt 的逐字复现**。
- **P2 `taxonomy`**：直接提供冻结标签定义和机械检查规则。
- **P3 `evidence_grounded`**：强制先定位可见事实，再形成 region/evidence/severity/label，
  但只输出统一 JSON，不输出隐藏推理过程。

三种 Prompt 共用相同 JSON Schema、图像和 token 上限。采样参数使用各 API 支持的
最低稳定随机性：四个配置均使用 temperature 0；Qwen 使用 Instruct 版本，Gemini
固定 `thinking_budget=0`，避免内部推理挤占结构化正文。GLM 保留该免费视觉模型的
服务端默认推理行为。所有差异写入 run manifest。

## 5. 模型条件

计划主比较包含四个已完成图片连通性核验的模型配置：

- Google `gemini-3.8-flash`：跨家族商业模型；
- SiliconFlow `Qwen/Qwen3-VL-8B-Instruct`：Qwen 小模型基线；
- SiliconFlow `Qwen/Qwen3-VL-32B-Instruct`：Qwen 同家族规模对照；
- Zhipu `glm-4.6v-flash`：免费视觉模型基线。

Qwen 8B/32B 构成同家族、同 Instruct 模式的规模效应比较；Gemini、Qwen、GLM 构成
跨家族比较，论文中不把三个家族直接描述为严格的弱/中/强梯度。正式开始前把实际
model ID、SDK 版本、base URL 和配置哈希写入 run manifest。不得使用 `latest` alias。

## 6. 输出与失败处理

- 统一输出结构见 `prediction_schema.json`。
- API 原始响应逐 attempt 只增不改；解析结果单独保存。
- Gemini 使用服务端 JSON Schema；Qwen 与 GLM 的 OpenAI-compatible 接口使用
  JSON Object mode，再执行相同的本地 Schema 与语义校验。
- JSON 解析、Schema 或语义校验失败均可重试，正式配置最多 5 次指数退避。
- 在严格校验前执行固定的表示归一化：若模型按区域重复输出同一标签，则合并为一条；
  严重度和置信度取该标签各观察中的最大值，region 合并，evidence 与修复建议取最严重且
  最高置信度的观察。若 `primary_issue != none`，冗余的 `no_issue_reason` 固定清空。
  若模型明确输出 `primary_issue=none` 但解释字段为空，填入固定中性说明；空的
  `audit_summary` 同样用不含新增判断的固定文本补齐。原始响应仍完整保存，归一化不新增
  或删除缺陷标签。若模型只报告 1 级问题却指定了主问题，则按冻结阈值将
  `primary_issue` 规范为 `none`，1 级问题本身仍保留。超过 Schema 字符上限的 region、
  evidence、recommended_action、no_issue_reason 和 audit_summary 从尾部确定性截断，避免
  因解释过长而重新调用模型。
- 最终失败记为 `api_error` / `parse_error` / `schema_error`，绝不能转换为 `none`。
- 断点续跑只跳过已有且通过校验的 parsed 结果。

## 7. 运行顺序与冻结

- 固定随机种子生成 `(sample, model, prompt)` 顺序。
- smoke 只用开发集，不对 Formal-88 调参。
- 正式运行规模为 88×4×3=1056 次主调用；失败重试不算新的实验样本。
- 正式运行启动后，不得依据 Formal-88 结果修改 Prompt、Schema 或阈值。

## 8. 重复性、成本与日志

- 主实验每格一次；另选固定开发子集进行 3 次重复，报告一致率。
- 保存开始/结束时间、延迟、token usage、provider request ID、错误类别和估算成本。
- run manifest 保存数据、Prompt、Schema、配置及代码文件 SHA-256。

## 9. 后续评分（不在本阶段运行）

- Natural-40：逐类 P/R/F1、micro/macro F1、Jaccard、exact match、Primary 指标与失败率。
- Controlled-48：目标缺陷召回率、control 虚报率、配对正确率及逐类结果。
- 置信区间按论文 pair bootstrap；同一图上的方法比较采用 paired bootstrap，必要时
  对二元配对结果使用 McNemar 检验。

## 10. 来源记录

- Paper2Poster 官方仓库固定提交：`623d042f283acee782b2644d6abd63f75eccfa1f`。
- 官方 critic Prompt 的定位与适配差异见 `prompts/P1_PROVENANCE.md`。
