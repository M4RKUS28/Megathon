document.addEventListener("DOMContentLoaded", () => {
  const passwordFields = document.querySelectorAll('input[type="password"]');
  passwordFields.forEach((field) => {
    field.setAttribute("minlength", "8");
    field.setAttribute("maxlength", "64");
  });

  const registerForm = document.getElementById("kc-register-form");
  const password = document.getElementById("password");
  const confirm = document.getElementById("password-confirm");
  if (!registerForm || !password || !confirm) return;

  const confirmGroup = confirm.closest(".form-group");
  if (confirmGroup) {
    confirmGroup.hidden = true;
    confirmGroup.setAttribute("aria-hidden", "true");
  }

  const mirrorPassword = () => {
    confirm.value = password.value;
  };

  mirrorPassword();
  password.addEventListener("input", mirrorPassword);
  registerForm.addEventListener("submit", mirrorPassword);
});
