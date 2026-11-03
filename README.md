# 视频建模素材库

为视频创作者和建模爱好者整理的 Blender 模型、建模源码与使用示例。

> 当前是仓库骨架：已建立五组素材的目录和整理清单，模型、源码和预览尚未迁入，尚无可下载的正式版本。使用许可尚待作者确定。

## 我想直接拿模型做视频

选一个主题 → 查看该主题的下载入口 → 下载带版本号的 Blender ZIP → 解压整个文件夹 → 打开 start.blend。
正式发布后，每个主题页面会列出文件大小、适用 Blender 版本、许可、预览图与固定版本下载链接。
GitHub 的绿色 Code → Download ZIP 和 Release 自动生成的 Source code 压缩包只包含仓库源码，不是模型下载包。

| 主题 | 内容 | 当前状态 |
| --- | --- | --- |
| [Mac Studio](models/mac-studio/README.md) | 主机结构、散热、爆炸拆解 | 整理中 |
| [ForceTouch](models/force-touch/README.md) | 触控板、线圈、应变片 | 整理中 |
| [Roadster](models/roadster/README.md) | 车辆与内部结构 | 整理中 |
| [手机摄像头](models/camera-optics/README.md) | 镜片、模组、手机、光线路径 | 整理中 |
| [3D 打印机](models/3d-printer/README.md) | 整机、喷头、传动、步进电机 | 整理中 |

## 我想修改模型或学习建模

各主题的 src/ 放建模源码和必需的小数据；examples/ 放最小示例；previews/ 放轻量预览。
源码迁入时保留原有模块和资源的相对层级，确认能独立运行后再重构。
克隆仓库不应触发模型大包下载，也不需要原视频工程、配音服务或远程渲染机器。

## 仓库结构

```text
video-model-library/
├── README.md
├── catalog.json
├── models/
│   ├── mac-studio/
│   ├── force-touch/
│   ├── roadster/
│   ├── camera-optics/
│   └── 3d-printer/
│       ├── README.md
│       ├── asset.json
│       ├── SOURCES.md
│       ├── src/
│       ├── examples/
│       └── previews/
├── docs/
│   ├── quick-start.md
│   ├── contributing.md
│   └── publishing.md
├── licenses/
│   └── README.md
└── .gitignore
```

五个主题使用同一套子目录结构。Blender、GLB、贴图大包等成品附件放 GitHub Releases，不进入 Git 历史。

- [下载与使用说明](docs/quick-start.md)
- [参与和反馈](docs/contributing.md)
- [维护者发布流程与大文件策略](docs/publishing.md)
- [许可状态](licenses/README.md)
