(function () {
  document.documentElement.style.display = "none";
  var KEY = "sb-supgrlinqgxvifijgbns-auth-token";
  try {
    var stored = localStorage.getItem(KEY);
    if (!stored) {
      window.location.href = "/auth/";
      return;
    }
    var parsed = JSON.parse(stored);
    if (!parsed || !parsed.access_token) {
      window.location.href = "/auth/";
      return;
    }
  } catch (e) {
    window.location.href = "/auth/";
    return;
  }
  document.documentElement.style.display = "";
})();
