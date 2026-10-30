// The page's icons, read once at start and kept in memory as data URLs: when the service goes
// away, the "no connection" notice must still show its icon (a state is an icon and a word).

const ICONS = {
  "--icon-logo": "generated/logo/primum-mark-mono.svg",
  "--icon-led": "generated/icons/i-led.svg",
  "--icon-panic": "generated/icons/i-panic.svg",
  "--icon-warn": "generated/icons/s-warn.svg",
};

export async function loadIcons(root) {
  await Promise.all(
    Object.entries(ICONS).map(async ([property, path]) => {
      const svg = await (await fetch(path)).text();
      root.style.setProperty(property, `url("data:image/svg+xml,${encodeURIComponent(svg)}")`);
    }),
  );
}
