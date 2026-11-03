# 建模源码

从仓库根目录运行 `blender -b --factory-startup --disable-autoexec --python models/mac-studio/src/build.py -- --out build/mac-studio --render`。

测试于 Blender 5.1.2。保留 tools/ 和当前 src/ 下的相对目录。模型生成不连接网络、不依赖原视频工程。

start.blend 是装配状态。exploded.blend 可直接查看内部层次，cutaway.blend 可查看剖面。EXPLODE_CTRL 的 explode 自定义属性控制展开程度；保持所有依赖集合一同导入。Max/Ultra 变体和展示用集合默认隐藏，请按需启用。
