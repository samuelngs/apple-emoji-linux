![AppleColorEmoji-ttf](https://repository-images.githubusercontent.com/158348890/3d33a645-a079-4150-860a-8cea647732b2)

语言：[English](README.md) | 简体中文

# apple-emoji-ttf

在 Linux、Windows 和网页中使用 Apple Color Emoji。

本仓库提供转换脚本、构建配置和发行包。由于版权原因，仓库里不包含 Apple 原始字体。自行构建时请从 macOS 获取 `Apple Color Emoji.ttc`。

## 说明

本项目仅供学习和研究使用。Apple Color Emoji 的字体资源和设计归 Apple Inc. 所有。Apple 是 Apple Inc. 在美国及其他国家和地区的注册商标。

跨系统或在网页中使用该字体可能涉及授权问题，请自行确认使用范围。

## 下载

不想自己构建的话，直接到 [Releases](https://github.com/samuelngs/apple-emoji-ttf/releases) 下载对应平台的文件：

- Ubuntu / Debian 用 `fonts-apple-color-emoji.deb`
- Fedora / RHEL 用 `fonts-apple-color-emoji.rpm`
- Arch Linux 用 `ttf-apple-emoji.pkg.tar.zst`
- Linux 手动安装用 `AppleColorEmoji-Linux.ttf`
- Windows 用 `AppleColorEmoji-Windows.ttf`
- Web 用法见下面的“Web”部分

## Linux

Ubuntu / Debian：

```bash
sudo dpkg -i fonts-apple-color-emoji.deb
# 或
sudo apt install ./fonts-apple-color-emoji.deb
```

Fedora / RHEL：

```bash
sudo dnf install ./fonts-apple-color-emoji.rpm
# 或
sudo rpm -i fonts-apple-color-emoji.rpm
```

Arch Linux：

```bash
sudo pacman -U ttf-apple-emoji.pkg.tar.zst
```

手动安装：

```bash
mkdir -p ~/.local/share/fonts
cp AppleColorEmoji-Linux.ttf ~/.local/share/fonts/
```

装好字体后，系统不一定会马上拿它显示 Emoji。很多桌面应用实际听 fontconfig 的排序。

先在 `/etc/fonts/conf.d/60-generic.conf`（或发行版对应文件）里找到 `<family>emoji</family>` 的 `<alias>`，把 Apple Color Emoji 放到 `<prefer>` 最前面：

```xml
<family>Apple Color Emoji</family>
```

再创建或更新 `~/.config/fontconfig/fonts.conf`。可以直接使用仓库里的 `fonts.conf`，让 serif、sans-serif、monospace 和 Noto Color Emoji 的请求优先走 Apple Color Emoji。

最后刷新缓存：

```bash
fc-cache -fv
```

## Windows

Windows 版本用于替换系统 Emoji 字体：

```text
C:\Windows\Fonts\seguiemj.ttf
```

请先备份原文件。这个字体不能像普通字体一样双击安装，需要手动替换。

如果文件被系统占用，可以在管理员命令提示符中执行：

```cmd
takeown /f "C:\Windows\Fonts\seguiemj.ttf"
icacls "C:\Windows\Fonts\seguiemj.ttf" /grant administrators:F
del "C:\Windows\Fonts\seguiemj.ttf"
copy "AppleColorEmoji-Windows.ttf" "C:\Windows\Fonts\seguiemj.ttf"
```

替换后重启系统。

## Web

Web 版本建议用 `configs/web.yaml` 单独构建。它不会只输出一个大字体文件，而是顺手生成 CSS，并把字体拆成多个分片，浏览器用到哪个 Emoji 再加载对应文件。

先构建：

```bash
python cli.py -c configs/web.yaml --output output/AppleColorEmoji.ttf
```

输出目录大概会长这样：

```text
output/
  AppleColorEmoji.css
  AppleColorEmoji[1].ttf
  AppleColorEmoji[2].ttf
  ...
```

部署时把这些文件放在同一个目录下，页面里引入 CSS：

```html
<link rel="stylesheet" href="/fonts/AppleColorEmoji.css">
```

然后在需要显示 Apple Emoji 的地方指定字体：

```css
.emoji {
  font-family: "Apple Color Emoji", system-ui, sans-serif;
}
```

如果你改了目录结构，记得同步改 `AppleColorEmoji.css` 里的 `src:` 路径。

## 自行构建

依赖：

- Python 3.12+
- `pip install -r requirements.txt`
- `Apple Color Emoji.ttc`

macOS 默认字体路径：

```text
/System/Library/Fonts/Apple Color Emoji.ttc
```

如果就在 macOS 上跑脚本，可以省掉 `--input`：

```bash
pip install -r requirements.txt
python cli.py -c configs/linux.yaml --output output/AppleColorEmoji-Linux.ttf
python cli.py -c configs/windows.yaml --output output/AppleColorEmoji-Windows.ttf
python cli.py -c configs/web.yaml --output output/AppleColorEmoji.ttf
```

如果字体文件在其他位置：

```bash
python cli.py -c configs/linux.yaml --input "/path/to/Apple Color Emoji.ttc" --output output/AppleColorEmoji-Linux.ttf
```

不同平台使用不同配置：

- `configs/linux.yaml`
- `configs/windows.yaml`
- `configs/web.yaml`

### 更新 Emoji 序列

```bash
python tools/update_emoji_data.py --version latest
# 或指定版本
python tools/update_emoji_data.py --version 17.0
```

也可以在构建前更新：

```bash
python cli.py -c configs/web.yaml --output output/AppleColorEmoji.ttf --update-sequences
python cli.py -c configs/windows.yaml --output output/AppleColorEmoji-Windows.ttf --update-sequences 17.0
```

`sequences/project-sequences.txt` 是项目维护的补充数据，不会从 Unicode 下载。

## 已知问题

- 部分 Linux 应用里的 Emoji 可能偏小。
- 部分 Qt 应用可能无法正确显示彩色 Emoji。

## 许可证

代码部分采用 [MIT License](LICENSE)。Apple Color Emoji 本身仍归 Apple 所有。
