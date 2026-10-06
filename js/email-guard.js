(() => {
  const decode = (el) => {
    const user = el.dataset.user;
    const domain = el.dataset.domain;
    if (!user || !domain) return "";
    return `${user}@${domain}`;
  };

  document.querySelectorAll(".email-guard").forEach((el) => {
    const address = decode(el);
    if (!address) return;

    if (!el.textContent.trim()) {
      el.textContent = address.replace("@", " [at] ");
    }

    el.addEventListener("click", (event) => {
      event.preventDefault();
      window.location.href = `mailto:${address}`;
    });
  });
})();
