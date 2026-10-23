// Apply before paint; blocked storage still leaves a usable light theme.
try {
  document.documentElement.dataset.theme =
    localStorage.getItem("kinetic.theme") || "light";
} catch {
  /* Browser privacy settings can disable storage. */
}
