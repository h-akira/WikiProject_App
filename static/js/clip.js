const targetLink = document.getElementById('share-link');
const copyButton = document.getElementById('copy-button');

copyButton.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(targetLink.href);
    alert('共有URLをリップボードにコピーしました');
  } catch (err) {
    alert('共有URLのクリップボードへのコピーに失敗しました');
    console.error('クリップボードへの書き込みに失敗しました:', err);
  }
});
