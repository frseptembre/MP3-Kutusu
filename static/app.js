'use strict';

const form = document.getElementById('converter-form');
const input = document.getElementById('video-url');
const submitButton = document.getElementById('convert-button');
const buttonLabel = submitButton.querySelector('.button-label');
const pasteButton = document.getElementById('paste-button');
const chooseFolderButton = document.getElementById('choose-folder');
const destinationName = document.getElementById('destination-name');
const destinationNote = document.getElementById('destination-note');
const statusBox = document.getElementById('status');
const statusText = document.getElementById('status-text');
const appKey = new URLSearchParams(window.location.search).get('key') || '';
let folderHandle = null;
let busy = false;

function status(message, type) {
  statusBox.hidden = false;
  statusBox.className = `status ${type || ''}`;
  statusText.textContent = message;
}

function nameFromHeaders(headers) {
  const contentDisposition = headers.get('Content-Disposition') || '';
  const matchUTF8 = /filename\*\s*=\s*utf-8''([^;]+)/i.exec(contentDisposition);
  const matchBasic = /filename\s*=\s*"?([^";]+)/i.exec(contentDisposition);
  let fileName = 'YouTube ses.mp3';
  try {
    if (matchUTF8) fileName = decodeURIComponent(matchUTF8[1]);
    else if (matchBasic) fileName = matchBasic[1];
  } catch (_) { /* use the default file name */ }
  return fileName.replace(/[\\/]/g, '').trim() || 'YouTube ses.mp3';
}

function saveToDownloads(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 60000);
}

async function saveToChosenFolder(blob, filename) {
  if (!folderHandle) return false;
  try {
    const fileHandle = await folderHandle.getFileHandle(filename, { create: true });
    const writable = await fileHandle.createWritable();
    await writable.write(blob);
    await writable.close();
    return true;
  } catch (error) {
    console.warn('Klasöre kayıt başarısız, İndirilenler kullanılıyor.', error);
    return false;
  }
}

if (typeof window.showDirectoryPicker === 'function') {
  chooseFolderButton.hidden = false;
  chooseFolderButton.addEventListener('click', async () => {
    try {
      folderHandle = await window.showDirectoryPicker({ mode: 'readwrite' });
      destinationName.textContent = `Seçilen klasör: ${folderHandle.name}`;
      destinationNote.textContent = 'Bundan sonraki MP3 dosyaları buraya kaydedilir.';
      status('Klasör seçildi. Artık video linkini yapıştırabilirsin.', '');
    } catch (error) {
      if (error.name !== 'AbortError') status('Klasör seçilemedi. İndirilenler klasörü kullanılacak.', 'error');
    }
  });
}

pasteButton.addEventListener('click', async () => {
  try {
    const text = await navigator.clipboard.readText();
    if (text) input.value = text.trim();
    input.focus();
  } catch (_) {
    status('Yapıştırma izni verilmedi. Linki kutuya Ctrl+V ile yapıştırabilirsin.', 'error');
    input.focus();
  }
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (busy) return;
  const url = input.value.trim();
  if (!url) {
    status('Önce YouTube bağlantısını kutuya yapıştır.', 'error');
    input.focus();
    return;
  }
  busy = true;
  submitButton.disabled = true;
  buttonLabel.textContent = 'MP3 HAZIRLANIYOR...';
  status('Video alınıyor ve MP3 hazırlanıyor. Biraz sürebilir.', 'loading');
  try {
    // Ask for directory permission while still in the button-click context.
    if (folderHandle && typeof folderHandle.queryPermission === 'function') {
      let permission = await folderHandle.queryPermission({ mode: 'readwrite' });
      if (permission !== 'granted' && typeof folderHandle.requestPermission === 'function') {
        permission = await folderHandle.requestPermission({ mode: 'readwrite' });
      }
      if (permission !== 'granted') {
        folderHandle = null;
        destinationName.textContent = 'İndirilenler klasörüne kaydedilir';
        destinationNote.textContent = 'Başka bir ayar yapmana gerek yok.';
      }
    }
    const response = await fetch('/api/convert', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-App-Key': appKey },
      body: JSON.stringify({ url }),
    });
    if (!response.ok) {
      let message = 'MP3 indirilemedi. Başka bir bağlantı deneyebilirsin.';
      try { const data = await response.json(); if (typeof data.detail === 'string') message = data.detail; }
      catch (_) { /* retain the friendly default */ }
      throw new Error(message);
    }
    const filename = nameFromHeaders(response.headers);
    const blob = await response.blob();
    status('Dosya hazır. Bilgisayarına kaydediliyor...', 'loading');
    const chosen = await saveToChosenFolder(blob, filename);
    if (!chosen) saveToDownloads(blob, filename);
    status(chosen ? `Hazır! “${filename}” seçtiğin klasöre kaydedildi.` : 'Hazır! İndirme başlatıldı. İndirilenler klasörünü kontrol et.', '');
  } catch (error) {
    status(error && error.message ? error.message : 'Bir hata oluştu. Tekrar dene.', 'error');
  } finally {
    busy = false;
    submitButton.disabled = false;
    buttonLabel.textContent = 'MP3 OLARAK İNDİR';
  }
});
