// ChatGPTにより生成
document.addEventListener("DOMContentLoaded", function() {
  // すべてのpublicおよびedit_permissionチェックボックスを取得
  let checkboxes = document.querySelectorAll('input[type="checkbox"][name*="public"], input[type="checkbox"][name*="edit_permission"]');

  checkboxes.forEach(function(checkbox) {
    // イベントリスナーを追加
    checkbox.addEventListener('change', function() {
      // チェックボックスのname属性から数字を抽出
      let num = checkbox.name.match(/\d+/)[0];

      // publicチェックボックスを取得
      let publicCheckbox = document.querySelector(`input[type="checkbox"][name="form-${num}-public"]`);
      // edit_permissionチェックボックスを取得
      let editPermissionCheckbox = document.querySelector(`input[type="checkbox"][name="form-${num}-edit_permission"]`);

      // Aがチェックされていない場合、Bのチェックを外す
      if (checkbox === publicCheckbox && !publicCheckbox.checked) {
        editPermissionCheckbox.checked = false;
      }

      // Bがチェックされた場合、Aをチェックする
      if (checkbox === editPermissionCheckbox && editPermissionCheckbox.checked) {
        publicCheckbox.checked = true;
      }
    });
  });
});
