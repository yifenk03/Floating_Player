
# 漂浮视频播放器

![界面](GUI.png)

## 当前环境说明

由于当前构建环境为Linux系统，打包生成的是Linux可执行文件。

**要生成Windows的exe文件，请按以下步骤操作：**

---

## Windows打包步骤

### 方法一：使用打包脚本（推荐）

1. 将整个项目文件夹复制到Windows电脑上

2. 双击运行 `pack_for_windows.bat`

3. 等待自动完成打包

4. 在 `dist\FloatingVideoPlayer\` 目录下找到 `FloatingVideoPlayer.exe`

### 方法二：手动打包

1. 在Windows上安装Python 3.8+
   - 下载地址: https://www.python.org/downloads/

2. 安装依赖：
   ```cmd
   pip install PyQt5 PyInstaller
   ```

3. 运行打包命令：
   ```cmd
   pyinstaller --onefile --name FloatingVideoPlayer --windowed floating_player.py
   ```

4. 可执行文件位置: `dist/FloatingVideoPlayer.exe`

---

## 功能特性

- ✓ 漂浮置顶窗口
- ✓ 无边框界面 (4px圆角)
- ✓ 支持拖放视频文件 (MP4, MKV, AVI, MOV, GIF等)
- ✓ 播放列表支持
- ✓ 视频自动播放下一个
- ✓ 浮动控制菜单（鼠标离开自动隐藏）
- ✓ 进度条控制
- ✓ 音量/静音控制
- ✓ 音频输出设备选择
- ✓ 键盘快捷键
- ✓ 4K显示器 150%显示优化

---

## 键盘快捷键

| 按键 | 功能 |
|------|------|
| Space | 播放/暂停 |
| ← | 后退10秒 |
| → | 前进10秒 |
| ↑ | 增加音量 |
| ↓ | 减少音量 |
| M | 静音切换 |
| O | 打开文件 |
| ESC | 关闭播放列表 |

---

## 使用说明

1. 运行程序
2. 拖放视频文件到窗口，或点击"打开"按钮选择文件
3. 支持拖放多个视频文件，自动加入播放列表
4. 鼠标移入显示控制菜单，3秒无操作自动隐藏
5. 点击右上角按钮可最小化或隐藏窗口
