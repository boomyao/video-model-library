# 使用示例

最小完整示例为 [../src/build.py](../src/build.py)，其中只调用本主题建模模块并生成可编辑模型。

start.blend 为完整模组；cutaway.blend 看内部结构；phone.blend 为手机外形；lens-rays.blend 查看镜片与光线。源码 Module.focus(mm) 与 Module.shift(x_mm,y_mm) 可控制对焦及平移，本版场景保持静态，不依赖逐帧回调。
