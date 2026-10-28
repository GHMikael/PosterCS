# External-Natural-20 外部自然海报测试协议 v1

日期：2026-09-30；技术输入附录更新：2026-10-08  
状态：样本素材与 Gold 已冻结；标准化输入已冻结，允许推理。

## 1. 目的

本实验用于回应 C48-Confirm 仅来自 PosterCS 生态的外部效度限制。它不重复证明 Source-aware Rule 或 Hybrid-v1 的内部性能，而是检验论文中最重要的 VLM 行为结论能否在非 PosterCS、作者制作的真实会议海报上观察到。

核心问题是：

1. Gemini-P2 与 Qwen32B-P3 在真实作者海报上的多标签缺陷识别表现如何；
2. 两个 operating point 是否仍表现出高频、缺乏区分度的缺陷指控；
3. 不同缺陷标签的 precision、recall 与误报模式是否与 Formal-88/C48 的方向一致。

## 2. 数据来源

- 数据集：`Paper2Poster/Paper2Poster` 官方 Hugging Face 数据集；
- 固定数据集 revision：`1dd57d40186caa38b71b766ad9ac08f3e801e4cb`；
- 数据集规模：100 篇论文及其作者制作的会议海报；
- 字段：标题、会议、年份、论文 URL、作者海报 URL、PaperQuiz；
- 许可：数据集卡标注为 MIT；原始 URL 和数据集 revision 一并保留。

该数据集中的 `image_url` 指向作者制作的真实会议海报，不是 PosterCS 输出，也不是本项目运行 Paper2Poster 后生成的海报。

## 3. 样本规模与确定性抽样

最终测试集包含 20 张海报，每篇论文只出现一次。

- ICLR：7 张；
- ICML：7 张；
- NeurIPS：6 张。

每个候选的排序键定义为：

```text
SHA256("postercs_external_natural20_v1|<dataset_revision>|<row_idx>|<title>")
```

各会议按该键升序选取。只允许因以下预先规定的技术原因跳过候选，并记录原因后顺延：

- URL 无法下载；
- 文件不是可解码的静态图像；
- 最长边小于 1000 像素，无法支持当前可读性标注；
- 与 PosterCS 既有论文标题完全或规范化后重复；
- 同一论文或同一海报重复出现。

不得因海报质量、缺陷多少、模型预测或是否“有代表性”而人工替换样本。

## 4. 输入与系统边界

本实验仅比较：

1. Gemini-P2；
2. Qwen32B-P3。

二者必须使用 Formal-88/C48 中已经冻结的 Prompt、输出 schema、严重度阈值和解析逻辑。不得根据 External-Natural-20 的 Gold 或预测结果修改 Prompt。

### 4.1 技术输入标准化附录（2026-10-08）

Gold 冻结后、任何预测内容被读取前，原始高分辨率作者海报的传输可行性检查显示：Qwen32B 的首张请求在长时间内未返回，而 Gemini 的整批原图试跑虽完成但不纳入结果。为避免模型间输入字节大小差异造成的技术性不公平，主运行改为使用同一套派生输入：每张原图保持原纵横比、无裁切、无拉伸，以 Lanczos 重采样将最长边限制为 2400 px，输出 PNG。

该操作只读取 image-only manifest，不读取 Gold 标签或任何模型预测；原始素材、样本选择和 Gold freeze 均不改变。派生图及逐图 SHA256、原始/派生尺寸保存在 `external_natural20_inference_preprocessing_v1.json`；主运行使用 `external_natural20_inference_manifest_v2_preprocessed.json`。原图试跑仅作为环境/传输日志，明确排除在分析、表格和论文结果之外。

不运行 Source-aware Rule-v1 或 Hybrid-v1，因为作者海报没有本项目可解析的 PPTX 源结构。Raster Rule-v1 也不纳入主比较，因为其阈值针对 16:9 PosterCS 画布校准，直接迁移到不同纵横比的真实会议海报会混入格式失配。该边界必须在论文中明确写出。

## 5. Gold 标注

沿用冻结的九标签自然海报 schema 与 moderate/severe 正例阈值：

- `body_text_too_small`
- `figure_detail_unreadable`
- `text_overload`
- `space_imbalance`
- `alignment_error`
- `weak_hierarchy`
- `overlap_or_clipping`
- `asset_missing_or_broken`
- `other`

标注采用：A 对 20 张全量盲标；B 对按会议和缺陷候选分层抽取的 10 张独立复标；分歧由第三轮仲裁解决。标注页面不显示模型输出。模型预测只能在 Gold 冻结并生成哈希后运行。

标注时以海报原始纵横比适配窗口显示，并记录显示器、浏览器窗口与缩放条件。轻微审美差异不记为 moderate/severe；只有明显降低快速扫读、局部辨认或信息获取效率的问题才进入正例。

## 6. 预注册指标

主指标：

- 多标签 micro precision、recall、F1；
- macro-F1，并明确零支持标签的处理；
- exact match；
- mean Jaccard；
- 每张海报的 allegation count；
- 对人工 Gold 为 `none` 的海报计算 any-defect false-positive rate（若存在）。

次指标：

- per-label precision、recall、F1 和整数分子/分母；
- primary-label accuracy；
- 两个 VLM 的标签频率分布；
- 失败、重试、延迟和估算成本。

由于 n=20，本实验定位为 post-freeze external validity check，不用于重新选择模型、Prompt 或阈值，也不宣称建立通用 benchmark。

## 7. 防泄漏与执行门

1. 下载并验证 20 张样本，完成来源、哈希、尺寸和排除日志；
2. 核实与全部开发/测试论文无重复；
3. 冻结样本 manifest；
4. 完成盲标、复标、仲裁和 agreement 报告；
5. 冻结 Gold manifest；
6. 才能运行两个 VLM；
7. 一次性评分，不回流调整现有系统。

## 8. 允许支持的论文结论

如果结果方向与内部实验一致，可以写成“小规模跨生态自然样本提供了方向一致的外部证据”。如果不一致，应原样报告，并将其解释为受控变异与真实海报任务之间的分布差异。

无论结果如何，本实验都不能证明 Source-aware Rule-v1 或 Hybrid-v1 跨生成器泛化，因为这些系统没有在该数据上运行。
