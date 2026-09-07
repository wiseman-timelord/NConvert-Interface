# NConvert-Interface
Status: Working - Recently had overhaul and assessment.

### Description:
Its a Python QTWeb Gradio interface for converting ANY image format to ANY imgage format, even rare ones like .pspimage, all made possible through NConvert binary command line tool. The program provides a user-friendly menu to set the source folder, input file format, and desired output format. The scripts ensures efficient and seamless conversion and management of image files, making it a practical tool for users needing to process multiple common format such as `.jpg`, `.bmp`, `.png`, etc, and also less common formats such as`.pspimage`, and vice versa, and another thing, it does this recursively through subfolders, so you can just aim it at windows pictures folder, and everything will be where it was, just in the new format too.

### Features:
- **Multiple Formats**: The Gradio interface limited to 10 image formats, but which ones can be edited in the `.py` script. 
- **Interactive Menu**: Utilizing your standard text-based menu for effective configuration.
- **Batch Conversion**: All specified format files in, specified folder and its subfolders, to desired format.
- **Automatic Report**: Provides a summary of the total number of successfully converted files.
- **Deletion Option**: Offers the option to delete original files.
- **Persistent Settings**: Remembers format from/to and target folder.
- **Error Handling**: Displays errors for any files that fail to convert.
- **Bleep On Complete**: Incase for some reasoning it is going to take a while.

### Preview:
- The Video Demonstration on YouTube (for v1.00)...
<br>[![NConvert-Batch on YouTube](./media/wisetime_youtube.jpg)](https://www.youtube.com/watch?v=ECydHjJ04U4)

- The NConvert-Interface main program display (v1.40)...
![Alternative text](https://github.com/wiseman-timelord/NConvertBatch/blob/main/media/gradio_interface.jpg)

## Requirements:
Needs re-assessment, however..
- Windows 10/11 -  "Windows 11 & 10: ✅ Fully Supported. This is the primary target for your current installer." -GLM
- [NConvert](https://www.xnview.com/en/nconvert) - ~500 image formats supported (installed by installer).
- Python 3.10-3.12 - Tested on, 3.10 and 3.12, but ensure python.exe is, on system PATH or in `C:\Program Files\Python3##" (where ## is the version).
- Powershell 5.1+ - Needs to be re-assessed for versioning, but its for the text buffer. 
- Internet - Installer requires internet for install of Python libraries etc.

### Instructions:
Here are my current instructions...
```
1. Downlaod latest release, and unpack to a suitable location.
2. Run `NConvert-Interface.Bat` by right click `Run as Administrator`, as we are doing, complex recursive file operations under the interface and downloading/unpacking NConvert in the installer. 
- It is optional to manually download/unpack NConvert to ".\data\NConvert\*", and the installer will detect it, but otherwise the installer would handle the download/install if there is no NConvert unpacked there. This may help if there are for some reason network issues.
3. Install Requirements from menu through option `2` on the batch menu, it will run `.\installer.py`, which will install everything you require via web/pip. 
4. After requirements are installed, then run `NConvert-Interface` from `1.` on the batch menu, and if the gradio interface does not pop-up in its own built-in browser window.
5. Configure the settings in the browser interface, if your file format preference is not in the list, then edit relevant lists in python script by replace appropriate extension text.
6. When all setting are correct, then 1st ensure you noticed the `Delete Original Files?` tickbox, and if you did, then click `Start Conversion`, and it will convert the files, as  you have specified, over-writing as it goes.
7. Check the image folders, I saved you potentially hours of work, but I did say I was a TimeLord ha.
```

### NOTATION:
- If you want to display, for example "AVIF" format, in the Windows Explorer thumbnails, then you should install [Icaros](https://github.com/Xanashi/Icaros/releases), then in the configuration add, in the case of the example ".avif", to the file extension list, and activate it.
- De-Confustion... Meaning 1: "Batch" - a `*.bat` Windows Batch file. Meaning 2: "Batch" - Repetitive actions done together in sequence.
- If you want other formats than the ones in the lists, because there are ~500 possible formats, then you will need to manually edit the top of ".\launcher.py".

### CREDITS:
- Thanks to, DeepSeek and GPT and Claud and Grok and Qwen and GLM, for assistance in programming. 
- Thanks to [XnView Software](https://www.xnview.com/en/) for, creating and hosting, [NConvert](https://www.xnview.com/en/nconvert/), the binary behind my frontend.
- NConvert-Batch is the Windows version of [NConvert-Bash](https://github.com/wiseman-timelord/NConvert-Bash).

### STRUCTURE:
- Pre-install...
```
.\NConvert-Interface.bat   (runs batch menu, producing options to install or launch.
.\launcher.py              (the main program)
.\installer.py             (the installer, run first).
```

### Development:
- If the program gets too big for one script (which is currently not the case), then create new `.\scripts\utilities.py`, and move all non core functions (list) out of launcher.py into utilities.
- Need additional option in batch menu, to launch without debug (command prompt) being open in background.

## DISCLAIMER:
This software is subject to the terms in License.Txt, covering usage, distribution, and modifications. For full details on your rights and obligations, refer to License.Txt.
NConvert is not made by Wiseman-Timelord, only the, Gradio Interface and Batch Launcher/Installer, is; Terms and Conditions, for NConvert still apply.
