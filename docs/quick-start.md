# 下载与使用

1. 在仓库首页按主题下载 Blender ZIP，不要下载 Source code 来找模型。
2. 解压完整文件夹，用 Blender 5.1.2 打开 start.blend。其他版本尚未测试。
3. 模型在 ASSET 集合，摄影机与灯光在 STUDIO 集合。各包的额外场景和控制方法见 README.txt。
4. 导入自己的工程：File → Append → 选择 .blend → Collection → ASSET。保留集合层级、控制器和依赖。
5. 注意单位：打印机包 1 单位 = 1 毫米，其他包以米为 Blender 单位。跨工程导入时检查尺寸并换算。
6. 使用时按 CC BY 4.0 署名并注明修改，第三方例外见 SOURCES.txt。

模型文件不含需自动运行的嵌入脚本。ForceTouch 的按压已保存为关键帧，其余多数模型保持静态；Python 控制接口不会自动变成时间线动画。
Blender 原生材质和节点保留；本版未提供 FBX/GLB 通用格式或完整视频工程。
