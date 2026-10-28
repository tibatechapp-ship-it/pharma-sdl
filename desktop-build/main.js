const { app, BrowserWindow, Menu } = require('electron');
const path = require('path');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 850,
    minWidth: 900,
    minHeight: 600,
    icon: path.join(__dirname, 'static', 'icon-512.png'),
    title: 'Pharma Lab — مختبر الفارما',
    backgroundColor: '#667eea',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  mainWindow.loadFile('index.html');

  const template = [
    {
      label: 'ملف',
      submenu: [
        { label: 'إعادة تحميل', role: 'reload' },
        { label: 'الوضع الكامل', role: 'togglefullscreen' },
        { type: 'separator' },
        { label: 'خروج', role: 'quit' },
      ],
    },
    {
      label: 'مساعدة',
      submenu: [
        {
          label: 'عن التطبيق',
          click: () => {
            const { dialog } = require('electron');
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'Pharma Lab',
              message: 'Pharma Lab v1.0.0',
              detail: 'مختبر الفارما الذاتي\nمن الكتاب إلى الكود — من النظرية إلى الاكتشاف\n\nMIT License © 2026',
            });
          },
        },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
