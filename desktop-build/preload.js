const { contextBridge } = require('electron');
contextBridge.exposeInMainWorld('pharmaLab', {
  platform: process.platform,
  version: process.versions.electron,
  isDesktop: true,
});
