# 建模源码

从仓库根目录运行 `blender -b --factory-startup --disable-autoexec --python models/roadster/src/build.py -- --out build/roadster --render`。

测试于 Blender 5.1.2。保留 tools/ 和当前 src/ 下的相对目录。模型生成不连接网络、不依赖原视频工程。

打开 start.blend。ASSET/Vehicle 内保留独立零件和原始命名，可隐藏车身面板查看内饰及结构。修改材质可在源码 car_mats.py 中进行；build.py 生成静态可编辑车辆。
