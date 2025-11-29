const c = document.getElementById("id_share");
const d = document.getElementById("id_share_edit_permission");
const shareEditPermission = document.getElementById("share-edit-permission");
const shareCode = document.getElementById("share-code");
// ページ読み込み時に実行
document.addEventListener('DOMContentLoaded', function() {
  // Aのチェック状態に応じてshareEditPermissionの表示を設定
  toggleD();
});
// Aがチェックされているかどうかをチェックする
function isCChecked() {
  return c.checked;
}
// Bのチェック状態と表示状態を制御する
function toggleD() {
  // Aがチェックされていない場合はBをチェック解除する
  if (!isCChecked()) {
    d.checked = false;
  }
  // Aがチェックされている場合はBを表示する
  shareEditPermission.style.display = isCChecked() ? "inline" : "none";
  shareCode.style.display = isCChecked() ? "inline" : "none";
}
// Aのチェック状態が変更されたときに呼び出される
c.addEventListener("change", toggleD);
