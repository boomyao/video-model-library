# 建模源码

从仓库根目录运行 `blender -b --factory-startup --disable-autoexec --python models/force-touch/src/build.py -- --out build/force-touch --render`。

测试于 Blender 5.1.2。保留 tools/ 和当前 src/ 下的相对目录。模型生成不连接网络、不依赖原视频工程。

打开 start.blend，时间线为 1–48 帧、24 fps。按空格播放，模组在第 15 帧发生位移，第 20 帧回到原位。该动画用于观察动作，不代表真实震动时序。源码 module.build_module(gap=0.3, floor=False) 可单独生成主体。
