(function () {
  const GITHUB_API = "https://api.github.com";
  const FALLBACK = "—";

  function formatVersion(tagName) {
    if (!tagName) return FALLBACK;
    return tagName.startsWith("v") ? tagName.slice(1) : tagName;
  }

  async function fetchLatestRelease(repo) {
    try {
      const res = await fetch(`${GITHUB_API}/repos/${repo}/releases/latest`, {
        headers: { Accept: "application/vnd.github+json" },
      });
      if (!res.ok) return null;
      const data = await res.json();
      return { tagName: data.tag_name, version: formatVersion(data.tag_name) };
    } catch {
      return null;
    }
  }

  function setReleaseLink(el, repo, release) {
    el.textContent = "";
    if (release) {
      const a = document.createElement("a");
      a.href = `https://github.com/${repo}/releases/tag/${release.tagName}`;
      a.textContent = release.version;
      a.rel = "noopener noreferrer";
      a.target = "_blank";
      el.appendChild(a);
    } else {
      el.textContent = FALLBACK;
    }
  }

  function updateVersions() {
    const elements = Array.from(document.querySelectorAll("[data-version-repo]"));
    const repos = [...new Set(elements.map((el) => el.getAttribute("data-version-repo")))];
    const cache = {};

    repos.forEach((repo) => {
      fetchLatestRelease(repo).then((release) => {
        cache[repo] = release;
        elements
          .filter((el) => el.getAttribute("data-version-repo") === repo)
          .forEach((el) => setReleaseLink(el, repo, release));
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", updateVersions);
  } else {
    updateVersions();
  }
})();
