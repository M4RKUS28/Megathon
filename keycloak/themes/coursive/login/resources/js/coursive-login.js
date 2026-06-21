document.addEventListener("DOMContentLoaded", () => {
  // ===== JUDGE HINT — remove this whole block to disable the demo credentials hint =====
  // Shows a small callout with demo login credentials on the sign-in and
  // sign-up pages so judges can log in quickly. Safe to delete entirely.
  (function injectJudgeHint() {
    const HINT_EMAIL = "creator@acme.test";
    const HINT_PASSWORD = "creator2026";
    const card = document.querySelector(".card-pf") || document.querySelector("#kc-content");
    if (!card || document.querySelector(".coursive-hint")) return;
    const hint = document.createElement("div");
    hint.className = "coursive-hint";
    hint.innerHTML =
      '<span class="coursive-hint__label">HINT</span>' +
      '<p class="coursive-hint__text">Demo login for judges:</p>' +
      '<dl class="coursive-hint__creds">' +
      '<dt>Email</dt><dd><code>' + HINT_EMAIL + "</code></dd>" +
      "<dt>Password</dt><dd><code>" + HINT_PASSWORD + "</code></dd>" +
      "</dl>";
    card.insertBefore(hint, card.firstChild);
  })();
  // ===== END JUDGE HINT =====

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
