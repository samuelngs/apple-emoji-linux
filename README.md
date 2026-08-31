# emoji-win

> **⚠️ EXPERIMENTAL PROJECT NOTICE**
> This project is **99% vibe-coded** (created by AI agent) and is highly **experimental**. While the current solution works great on the latest Windows 11 and using browser apps, some native apps still don't use converted emojies. Project requires further investigation and testing. Use at your own risk and always backup your system fonts before proceeding.

<img width="420" height="729" alt="apple emoji win on demo" src="https://github.com/user-attachments/assets/6c78d21d-e22b-459e-8f67-4f0fdaf7125d" />

</br>

## 🍎 Why emoji-win?

**Tired of Windows 11's bland default emojis?** Want the beautiful, expressive Apple emojis on your Windows machine? You're in the right place!

Windows 11 comes with basic, flat emojis that lack personality. Meanwhile, Apple's emojis are colorful, detailed, and full of character. This tool bridges that gap by converting Apple Color Emoji fonts to work perfectly on Windows 11.

### Perfect for:
- 🎨 **Designers** who want consistent emoji appearance across platforms
- 💬 **Content creators** who need expressive emojis for social media
- 👥 **Anyone** who's tired of Windows' lackluster emoji design
- 🔄 **Mac users** who want familiar emojis on their Windows machines

Transform your Windows emoji experience from bland to brilliant! 🚀

## ✨ Features

- ✅ **Full Windows compatibility** - No more "file is not a font" errors
- ✅ **Complete emoji coverage** - All 1,400+ emojis work properly
- ✅ **Enhanced app compatibility** - Works with Telegram, Discord, browsers, and more
- ✅ **Advanced font registration** - Multiple registry entries for maximum compatibility
- ✅ **Proper font structure** - Follows Windows Segoe UI Emoji patterns
- ✅ **Easy to use** - Simple command-line interface

## 🚀 Quick Start

### Super Quick (One-liner workflow)
```bash
# 1. Clone and enter directory
git clone https://github.com/jjjuk/emoji-win.git && cd emoji-win

# 2. Download AppleColorEmoji.ttf from apple-emoji-linux releases to fonts/ directory

# 3. Convert (easiest way)
./convert.sh

# OR convert with direct command (dependencies handled automatically)
uv run python main.py fonts/AppleColorEmoji.ttf fonts/AppleColorEmojiForWindows.ttf
```

### Prerequisites
- Python 3.11+
- `uv` (recommended) or `pip`

### Installation

**One-liner with uv (recommended):**
```bash
git clone https://github.com/jjjuk/emoji-win.git && cd emoji-win
```

**Alternative with pip:**
```bash
git clone https://github.com/jjjuk/emoji-win.git
cd emoji-win
pip install fonttools
```

### Usage

**Easiest way (shell script):**
```bash
./convert.sh  # Uses default paths: fonts/AppleColorEmoji.ttf → fonts/SegoeUIEmoji.ttf
# OR specify custom paths:
./convert.sh /path/to/AppleColorEmoji.ttf /path/to/output.ttf
```

**Direct command (uv handles dependencies automatically):**
```bash
uv run python main.py input_apple_font.ttf output_windows_font.ttf
```

**With regular python:**
```bash
python main.py input_apple_font.ttf output_windows_font.ttf
```

**Example:**
```bash
# Download AppleColorEmoji.ttf from apple-emoji-linux releases first
uv run python main.py AppleColorEmoji.ttf SegoeUIEmoji.ttf
```

## 📥 Getting Required Fonts

### 1. Apple Color Emoji Font (Required)

The easiest way to get the Apple Color Emoji font is from the **apple-emoji-linux** project:

**🔗 https://github.com/samuelngs/apple-emoji-linux/releases**

- Download the latest `AppleColorEmoji.ttf` from their releases
- **Place it in**: `fonts/AppleColorEmoji.ttf`

### 2. Windows Segoe UI Emoji Font (Optional but Recommended)

For best DirectWrite compatibility (Windows Terminal, Telegram Desktop, modern apps):

- **Extract from Windows**: Copy `seguiemj.ttf` from `C:\Windows\Fonts\` on any Windows system
- **Place it in**: `fonts/seguiemj.ttf`
- **Why needed**: Provides COLR/CPAL tables for modern Windows applications

### Alternative Sources

You can also obtain the Apple font from:
- macOS system (`/System/Library/Fonts/Apple Color Emoji.ttc`)
- iOS device backup
- Other legitimate sources

**Note**: This tool only converts fonts you already own legally.

##   Getting Original Windows Emoji Font (Optional)

If you want to extract the original Windows Segoe UI Emoji font for comparison or backup:

### From Windows 11 ISO

1. **Download Windows 11 ISO** from Microsoft's official website
2. **Mount the ISO** (right-click → Mount)
3. **Extract the font:**
   ```cmd
   # Navigate to mounted drive (e.g., D:)
   copy "D:\sources\install.wim" "C:\temp\install.wim"

   # Use DISM to extract (requires Windows SDK or ADK)
   dism /mount-image /imagefile:"C:\temp\install.wim" /index:1 /mountdir:"C:\temp\mount"
   copy "C:\temp\mount\Windows\Fonts\seguiemj.ttf" "C:\temp\seguiemj_from_iso.ttf"
   dism /unmount-image /mountdir:"C:\temp\mount" /discard
   ```

### From Running Windows System

Simply copy from your current Windows installation:
```cmd
copy "C:\Windows\Fonts\seguiemj.ttf" "C:\backup\seguiemj_current.ttf"
```

**Legal Note**: The Windows Segoe UI Emoji font is proprietary to Microsoft. Only extract/use if you have a valid Windows license.

##  💻 Windows Font Management

###   Easy Method: Use the Batch Script

We provide a Windows batch script that automates the entire process:

1. **Download `windows_font_manager.bat`** from this repository
2. **Create a `fonts` folder** in the same directory as the batch file
3. **Place `AppleColorEmojiForWindows.ttf` in the fonts folder**
4. **Double-click `windows_font_manager.bat`** (auto-elevates to administrator)
5. **Choose your action:**
   - **Option 1: INSTALL** - Backup original font + install Apple emoji font + clear cache
   - **Option 2: RESTORE** - Restore original Windows font + clear cache

### 🔄 Manual Installation Process

#### Step 1: Backup Original Windows Emoji Font

**⚠️ CRITICAL: Always backup before making changes!**

1. **Create backup directory:**
   ```cmd
   mkdir C:\FontBackup
   ```

2. **Copy original Segoe UI Emoji font:**
   ```cmd
   copy "C:\Windows\Fonts\seguiemj.ttf" "C:\FontBackup\seguiemj_original.ttf"
   ```

3. **Export font registry entries:**
   ```cmd
   reg export "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts" "C:\FontBackup\fonts_registry_backup.reg"
   ```

#### Step 2: Remove Original Font (Optional)

**Note:** You can install alongside the original font, but replacing gives better results.

1. **Open Command Prompt as Administrator**

2. **Remove font file:**
   ```cmd
   takeown /f "C:\Windows\Fonts\seguiemj.ttf"
   icacls "C:\Windows\Fonts\seguiemj.ttf" /grant administrators:F
   del "C:\Windows\Fonts\seguiemj.ttf"
   ```

3. **Remove registry entry:**
   ```cmd
   reg delete "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts" /v "Segoe UI Emoji (TrueType)" /f
   ```

#### Step 3: Install Converted Font

1. **Run the converter:**
   ```bash
   python main.py AppleColorEmoji.ttf SegoeUIEmoji.ttf
   ```

2. **Copy to Windows Fonts directory:**
   ```cmd
   copy "SegoeUIEmoji.ttf" "C:\Windows\Fonts\seguiemj.ttf"
   ```

3. **Add registry entry:**
   ```cmd
   reg add "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts" /v "Segoe UI Emoji (TrueType)" /t REG_SZ /d "seguiemj.ttf" /f
   ```

4. **Restart Windows** (recommended) or restart applications

### 🔙 Restoring Original Font

If you need to restore the original Windows emoji font:

1. **Remove converted font:**
   ```cmd
   del "C:\Windows\Fonts\seguiemj.ttf"
   reg delete "HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts" /v "Segoe UI Emoji (TrueType)" /f
   ```

2. **Restore original font:**
   ```cmd
   copy "C:\FontBackup\seguiemj_original.ttf" "C:\Windows\Fonts\seguiemj.ttf"
   ```

3. **Restore registry:**
   ```cmd
   reg import "C:\FontBackup\fonts_registry_backup.reg"
   ```

4. **Restart Windows**

### 🛡️ Safety Notes

- **Always run as Administrator** when modifying system fonts
- **Create System Restore Point** before making changes
- **Keep backups safe** - store them outside C:\ drive if possible
- **Test in safe mode** if you encounter issues
- **This is experimental** - the process works on latest Windows 11 but needs more testing

### 🔧 Troubleshooting

**Font not showing up:**
- Restart Windows completely (not just applications)
- Clear font cache: `del /q /s %windir%\ServiceProfiles\LocalService\AppData\Local\FontCache\*`
- Check if font is properly registered in registry

**Application-specific issues (Telegram, Discord, etc.):**
- See detailed solutions in [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Enhanced registry entries now automatically added for better app compatibility
- Clear application-specific caches and restart apps

**System instability:**
- Boot into Safe Mode
- Restore original font from backup
- Use System Restore if needed

**Permission errors:**
- Ensure running as Administrator
- Check if font file is in use by another process
- Temporarily disable antivirus during installation

## 🔧 How It Works

The converter fixes several Windows compatibility issues:

### Font Recognition
- Creates required `glyf` and `loca` tables for Windows font recognition
- Adds proper Windows Unicode BMP cmap subtable
- Updates font metadata (OS/2, name, head, post tables)

### Emoji Coverage
- Preserves all original emoji characters (1,400+)
- Uses proper Unicode cmap structure that Windows expects
- Maintains Apple's high-quality emoji artwork

### Windows Integration
- Mimics Segoe UI Emoji font naming for seamless replacement
- Follows Windows font structure patterns
- Compatible with all Windows applications

## 📋 Requirements

- **Python 3.11+**
- **uv** (recommended) or **pip** for dependency management
- **Apple Color Emoji font** (user must provide legally)
- **Windows 11** (tested and working on latest version)
- **Administrator privileges** (for font installation)

**Note**: Dependencies are automatically handled when using `uv run`

## ⚖️ Legal & Licensing

### This Tool (MIT License)
This conversion tool is open source under the MIT License. You're free to use, modify, and distribute it.

### Font Licensing Important Notes

**Apple Fonts**: Apple Color Emoji is proprietary to Apple Inc. You may only use it if you have a legal license (e.g., owning a Mac/iOS device). This tool does not provide or distribute Apple fonts. We recommend using the [apple-emoji-linux](https://github.com/samuelngs/apple-emoji-linux) project to obtain the font legally.

**Windows Fonts**: Windows Segoe UI Emoji is proprietary to Microsoft. Do not redistribute Windows system fonts.

**Your Responsibility**: Ensure you have legal rights to any fonts you convert. This tool is for personal use and legitimate font conversion only.

### What You Can Do
- ✅ Use this tool to convert fonts you legally own
- ✅ Share this conversion tool
- ✅ Modify and improve this tool

### What You Cannot Do
- ❌ Distribute Apple or Microsoft fonts without permission
- ❌ Use this for commercial font piracy
- ❌ Claim ownership of proprietary font designs

## 🙏 Acknowledgments

This project builds upon the excellent work of:

- **[apple-emoji-linux](https://github.com/samuelngs/apple-emoji-linux)** by [@samuelngs](https://github.com/samuelngs) - Provides extracted Apple Color Emoji fonts that make this conversion possible. This project is essential for accessing Apple emoji fonts on non-Apple systems.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Disclaimer**: This tool is for educational and personal use. Users are responsible for ensuring they have appropriate licenses for any fonts you convert.
