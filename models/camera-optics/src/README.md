# 建模源码

从仓库根目录运行 `blender -b --factory-startup --disable-autoexec --python models/camera-optics/src/build.py -- --out build/camera-optics --render`。

测试于 Blender 5.1.2。保留 tools/ 和当前 src/ 下的相对目录。模型生成不连接网络、不依赖原视频工程。

start.blend 为完整模组；cutaway.blend 看内部结构；phone.blend 为手机外形；lens-rays.blend 查看镜片与光线。源码 Module.focus(mm) 与 Module.shift(x_mm,y_mm) 可控制对焦及平移，本版场景保持静态，不依赖逐帧回调。
