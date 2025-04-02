# Required Font Files for Offline Usage

For this application to work properly in air-gapped environments (without internet access), you need to download the following font files and place them in this directory:

## Material Icons Fonts
Download from: https://fonts.gstatic.com/s/materialicons/v140/flUhRq6tzZclQEJ-Vdg-IuiaDsNcIhQ8tQ.woff2
Save as: `material-icons.woff2`

## Roboto Fonts
Download the following files:

1. Roboto Light (300):
   - URL: https://fonts.gstatic.com/s/roboto/v30/KFOlCnqEu92Fr1MmSU5fBBc4.woff2
   - Save as: `roboto-v30-latin-300.woff2`

2. Roboto Regular (400):
   - URL: https://fonts.gstatic.com/s/roboto/v30/KFOmCnqEu92Fr1Mu4mxK.woff2
   - Save as: `roboto-v30-latin-regular.woff2`

3. Roboto Medium (500):
   - URL: https://fonts.gstatic.com/s/roboto/v30/KFOlCnqEu92Fr1MmEU9fBBc4.woff2
   - Save as: `roboto-v30-latin-500.woff2`

4. Roboto Bold (700):
   - URL: https://fonts.gstatic.com/s/roboto/v30/KFOlCnqEu92Fr1MmWUlfBBc4.woff2
   - Save as: `roboto-v30-latin-700.woff2`

## How to Download

You can download these files using any of the following methods:

### Using a Web Browser
1. Copy each URL
2. Paste it into your browser's address bar
3. The browser will download the file
4. Rename the downloaded file to the specified name
5. Move it to this directory

### Using PowerShell (Windows)
```powershell
Invoke-WebRequest -Uri "https://fonts.gstatic.com/s/materialicons/v140/flUhRq6tzZclQEJ-Vdg-IuiaDsNcIhQ8tQ.woff2" -OutFile "material-icons.woff2"
Invoke-WebRequest -Uri "https://fonts.gstatic.com/s/roboto/v30/KFOlCnqEu92Fr1MmSU5fBBc4.woff2" -OutFile "roboto-v30-latin-300.woff2"
Invoke-WebRequest -Uri "https://fonts.gstatic.com/s/roboto/v30/KFOmCnqEu92Fr1Mu4mxK.woff2" -OutFile "roboto-v30-latin-regular.woff2"
Invoke-WebRequest -Uri "https://fonts.gstatic.com/s/roboto/v30/KFOlCnqEu92Fr1MmEU9fBBc4.woff2" -OutFile "roboto-v30-latin-500.woff2"
Invoke-WebRequest -Uri "https://fonts.gstatic.com/s/roboto/v30/KFOlCnqEu92Fr1MmWUlfBBc4.woff2" -OutFile "roboto-v30-latin-700.woff2"
```

### Using Wget (Linux/macOS)
```bash
wget -O material-icons.woff2 "https://fonts.gstatic.com/s/materialicons/v140/flUhRq6tzZclQEJ-Vdg-IuiaDsNcIhQ8tQ.woff2"
wget -O roboto-v30-latin-300.woff2 "https://fonts.gstatic.com/s/roboto/v30/KFOlCnqEu92Fr1MmSU5fBBc4.woff2"
wget -O roboto-v30-latin-regular.woff2 "https://fonts.gstatic.com/s/roboto/v30/KFOmCnqEu92Fr1Mu4mxK.woff2"
wget -O roboto-v30-latin-500.woff2 "https://fonts.gstatic.com/s/roboto/v30/KFOlCnqEu92Fr1MmEU9fBBc4.woff2"
wget -O roboto-v30-latin-700.woff2 "https://fonts.gstatic.com/s/roboto/v30/KFOlCnqEu92Fr1MmWUlfBBc4.woff2"
```

Once these files are in place, the application will be able to run completely offline without requiring internet access for fonts and icons. 