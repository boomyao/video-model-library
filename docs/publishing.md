# 发布与大文件策略

核对日期：2026-11-03。平台限制后续可能变化，以官方页面为准。

## 存放位置

| 内容 | 存放位置 |
| --- | --- |
| 建模 Python、必要的小 JSON 数据、说明、轻量预览 | Git 仓库 |
| Blender 成品模型、必要贴图、可选通用格式、示例场景 | GitHub Releases 附件 |
| 视频成片、渲染帧、模拟缓存、历史备份、原始调研资料 | 制作归档，不进默认素材包 |
| 单个合理拆分后仍超过 2 GiB 的资产或备用镜像 | 外部下载服务，主题页面记录版本、大小与 SHA-256 |

模型文件即使小于 100 MiB，也按统一方式放 Releases，避免二进制版本累积进 Git 历史。
不要上传整个 cuts 工程压缩包。先按模型内容分包，超大纹理或电影场景再作为可选包；优先语义拆包，不优先做难用的分卷压缩。

## GitHub 限制

- 普通 Git：超过 50 MiB 警告，超过 100 MiB 阻止；网页上传单文件不超过 25 MiB。
- Releases：按 Releases 专门文档，每个附件小于 2 GiB，每个 Release 最多 1,000 个附件；文档未设置 Release 总体积和下载带宽上限。
- Git LFS：Free/Pro 的单文件上限为 2 GB；Free/Pro 当前各包含 10 GiB 存储及每月 10 GiB 下载带宽。模型每次更新保存完整新版本，观众下载计入仓库所有者的带宽。

本项目默认用 Releases。只有今后确实要多人在 Git 中共同维护大型二进制文件，才评估 LFS 与预算。

来源：
- https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github
- https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
- https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage
- https://docs.github.com/en/billing/concepts/product-billing/git-lfs

## 每组独立发版

Tag 示例：mac-studio-v1.0.0、force-touch-v1.0.0。一个主题更新不要求其余主题重新打包。
Tag 对应生成该次模型包的源码提交；发布后不要用新文件覆盖同一版本的旧附件，有修复就发新版本。
主题 README 使用带 tag 的固定版本链接，不能让五组模型共用 releases/latest/download，因为 latest 可能属于另一主题。

附件命名示例：

```text
mac-studio-v1.0.0-blender.zip
mac-studio-v1.0.0-studio.zip       # 可选，确有额外示例场景时提供
mac-studio-v1.0.0-glb.zip          # 可选，已验证导出效果时提供
SHA256SUMS.txt
```

Release 自动生成的 Source code (zip/tar.gz) 是源码快照，不是直接使用包；在 Release 说明中明确指出该下载哪个附件。

## 实际发布步骤

1. 将对应工程的模型源码及必要依赖迁入该主题 src/，独立运行，去掉对私人绝对路径及原视频制作流水线的依赖。
2. 在单独的导出工作目录生成模型，确保默认状态好用；分组 ASSET/STUDIO，注明比例、方向和控制器。
3. 打包必要的外部资源。脚本逐帧驱动的运动如要直接播放，需转换为关键帧；模拟缓存单独处理。
4. 从一个新目录解压，用标注的 Blender 版本重新打开，检查缺失依赖、材质、可见性、比例和控制；至少查看一个实际渲染预览。
5. 随包加入许可、来源、模型用途和简短操作说明。未完成许可范围确认的资产不混入正式包。
6. 给每个 ZIP 算 SHA-256，记录大小；单个附件留出余量，控制在 2 GiB 以下。
7. 更新 asset.json 的版本、Blender 测试版本、包文件名、字节数、校验值及最终下载地址，更新主题 README 下载入口和真实预览。
8. 提交源码与说明，打对应 tag，在 GitHub 的 Releases → Draft a new release 选择该 tag，上传 ZIP 与 SHA256SUMS.txt。
9. 完成附件和说明核对后发布，再从下载链接抽查下载和解压。仓库骨架上传不等于模型包已发布；模型发版状态以各主题页面和 Releases 为准。

最终下载地址示例结构（OWNER/REPO 必须替换）：
https://github.com/OWNER/REPO/releases/download/mac-studio-v1.0.0/mac-studio-v1.0.0-blender.zip
