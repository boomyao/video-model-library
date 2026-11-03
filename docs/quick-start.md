# 下载与使用

当前还没有正式模型包，以下是发布后的使用约定。

1. 在首页选择一个模型主题。
2. 按该主题页面注明的版本，下载 xxx-vX.Y.Z-blender.zip；不需要安装 Git 或 Git LFS。
3. 解压整个压缩包，保留 start.blend 与 textures/ 等文件的相对位置。
4. 查看包内 README.txt 中测试过的 Blender 版本、单位、方向与使用许可。
5. 打开 start.blend。模型主体放在 ASSET 集合，灯光、摄影机和背景分别放在 STUDIO 集合。
6. 需要导入自己的项目时，在 Blender 中通过 Append 选取 ASSET 集合，连同控制器一起导入。

ASSET/STUDIO 是待整理时采用的命名约定，不保证目前原工程已有这些集合。
程序化材质与剖切控制优先使用 Blender 原生文件；通用格式仅在单独导出并验证之后提供。

## 下载包的约定

```text
mac-studio-v1.0.0-blender/
├── start.blend
├── README.txt
├── LICENSE.txt
├── SOURCES.txt
└── textures/       # 有外部贴图时提供；可打包的依赖优先打包进 blend
```

版本号和目录仅作示例，不表示已经发布。模型包的许可与外部资产许可必须随包附带。
可选的大型演示场景另做 studio.zip；不要为了使用一个模型要求下载全部五组素材。
