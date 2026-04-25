# 第二阶段（开发阶段）交付物清单与提交说明

**截止时间**：2026-05-03（第 9 周）
**编制日期**：2026-04-19

---

## 1. 交付物清单

| # | 类型 | 文件名（按命名规范） | 来源草稿 |
|---|------|---------------------|---------|
| 1 | 团队 | `03小组_开发阶段小组沟通交流记录.pdf` | `03小组_开发阶段小组沟通交流记录.md` |
| 2 | 团队 | `03小组_小组开发任务划分说明.pdf` | `03小组_小组开发任务划分说明.md` |
| 3 | 个人 | `软件综合实训_24281153_朱思思_后端模块源代码.rar` | 由 `backend/` 目录打包，附带 `源代码说明.md` 转 PDF |
| 4 | 个人 | `软件综合实训_24281153_朱思思_单元测试报告.pdf` | `软件综合实训_24281153_朱思思_单元测试报告.md` |
| 5 | 个人 | `软件综合实训_24281153_朱思思_开发阶段实训报告.pdf` | `软件综合实训_24281153_朱思思_开发阶段实训报告.md` |

宋嘉桐、贾文霞需要各自准备：
- `软件综合实训_[学号]_[姓名]_XXX模块源代码.rar`
- `软件综合实训_[学号]_[姓名]_单元测试报告.pdf`
- `软件综合实训_[学号]_[姓名]_开发阶段实训报告.pdf`

---

## 2. Markdown 转 PDF（pandoc 方案）

```bash
brew install pandoc
brew install --cask mactex   # 第一次需要装 LaTeX，约 4GB
```

转换单个文件：
```bash
cd docs/phase2
pandoc "软件综合实训_24281153_朱思思_单元测试报告.md" \
       -o "软件综合实训_24281153_朱思思_单元测试报告.pdf" \
       --pdf-engine=xelatex \
       -V CJKmainfont="PingFang SC" \
       -V mainfont="PingFang SC" \
       -V geometry:margin=2.5cm \
       --toc
```

批量转换所有 md：
```bash
cd docs/phase2
for f in *.md; do
  [ "$f" = "README.md" ] && continue
  pandoc "$f" -o "${f%.md}.pdf" --pdf-engine=xelatex \
    -V CJKmainfont="PingFang SC" -V mainfont="PingFang SC" \
    -V geometry:margin=2.5cm --toc
done
```

> 如果不想装 LaTeX，可以打开 md 直接用 Typora / Mark Text / VS Code 预览后"另存为 PDF"。

---

## 3. 后端源代码 RAR 打包

macOS 默认不带 rar，先装：
```bash
brew install rar
```

然后打包：
```bash
cd /Users/sissi/PycharmProjects/Canteen
# 把源代码说明也带上
cp docs/phase2/源代码说明.pdf backend/源代码说明.pdf

rar a "软件综合实训_24281153_朱思思_后端模块源代码.rar" \
      backend/ \
      -x"backend/__pycache__" \
      -x"backend/**/__pycache__" \
      -x"backend/.pytest_cache"

rm backend/源代码说明.pdf
```

如果不想装 rar，提交 zip 也是可以的（命名规范允许 `.rar/zip`）：
```bash
cd /Users/sissi/PycharmProjects/Canteen
cp docs/phase2/源代码说明.pdf backend/源代码说明.pdf
zip -r "软件综合实训_24281153_朱思思_后端模块源代码.zip" backend/ \
       -x "backend/__pycache__/*" "backend/**/__pycache__/*" \
       -x "backend/.pytest_cache/*"
rm backend/源代码说明.pdf
```

---

## 4. 提交前自查清单

- [ ] 文件名严格匹配命名规范（中括号要去掉，下划线分隔，无空格）
- [ ] PDF 文件能正常打开，中文显示正常
- [ ] 沟通交流记录的真实时间 / 地点 / 议定细节已补充
- [ ] 任务划分说明里的队友学号已补全
- [ ] 单元测试报告里的"实际结果"列与最新一次跑的输出一致
- [ ] 个人开发阶段报告的反思部分有具体的"事 + 思考"，不是套话
- [ ] 源代码 RAR 内不含 `__pycache__` / `.venv` / `database/*.db`
- [ ] 所有 PDF 已上传到课程平台

---

## 5. 时间线建议

| 日期 | 事项 |
|------|------|
| 2026-04-19（今天）| 完成所有文档草稿 + 跑通 pytest |
| 2026-04-22 | 三人各自完成本人开发阶段报告草稿 |
| 2026-04-26 | 小组互评，沟通交流记录补真实细节 |
| 2026-04-30 | 全部 markdown 转 PDF，源代码打包 |
| 2026-05-02 | 上传课程平台 |
| 2026-05-03 | 截止日，最终核对 |
