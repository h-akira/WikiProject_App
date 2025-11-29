const a = document.getElementById("id_public");
const b = document.getElementById("id_edit_permission");
const editPermission = document.getElementById("edit-permission");
// ページ読み込み時に実行
document.addEventListener('DOMContentLoaded', function() {
  // Aのチェック状態に応じてeditPermissionの表示を設定
  toggleB();
});
// Aがチェックされているかどうかをチェックする
function isAChecked() {
  return a.checked;
}
// Bのチェック状態と表示状態を制御する
function toggleB() {
  // Aがチェックされていない場合はBをチェック解除する
  if (!isAChecked()) {
    b.checked = false;
  }
  // Aがチェックされている場合はBを表示する
  editPermission.style.display = isAChecked() ? "inline" : "none";
}
// Aのチェック状態が変更されたときに呼び出される
a.addEventListener("change", toggleB);
