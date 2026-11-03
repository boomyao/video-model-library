# 可选光学计算工具

模型生成直接读取随仓库提供的 ../assets/lens_US10302915_e1.json，无需重新抓取或计算。
如需重新计算专利镜头，先从 SOURCES.md 中的 Google Patents 链接保存完整 HTML，再在独立 Python 环境安装 numpy、beautifulsoup4、matplotlib，运行：

```sh
python lens_trace.py patent.html 1 output.png
```

会生成 output.png 与 output.json。页面结构变更可能影响表格解析；这些工具保留原工程算法，本次发布的模型验证使用已生成的 JSON。
optics_data.py [output.json] 为额外的光学示意数据导出工具，不是加载模型的依赖。
