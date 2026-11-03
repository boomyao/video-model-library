# 建模源码

从仓库根目录运行 `blender -b --factory-startup --disable-autoexec --python models/3d-printer/src/build.py -- --out build/3d-printer --render`。

测试于 Blender 5.1.2。保留 tools/ 和当前 src/ 下的相对目录。模型生成不连接网络、不依赖原视频工程。

start.blend 为整机，gantry.blend 为运动机构，stepper-cutaway.blend 为电机剖面。单位为毫米（1 Blender 单位 = 1 mm）；与其他包合并时保留或正确换算单位。源码整机.整机().pose(x=...,y=...,z=...) 控制喷头姿态；动画需对相关物体写入关键帧或从脚本逐帧生成。
