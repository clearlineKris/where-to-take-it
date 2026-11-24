(function () {
  "use strict";

  function params() {
    try {
      return new URLSearchParams(window.location.search);
    } catch (err) {
      return new URLSearchParams();
    }
  }

  function setHidden(el, hidden) {
    el.classList.toggle("is-hidden", hidden);
    if (hidden) el.setAttribute("hidden", "");
    else el.removeAttribute("hidden");
  }

  function apply(root) {
    var input = root.querySelector("[data-filter-input]");
    var status = root.querySelector("[data-filter-status]");
    var empty = root.querySelector("[data-filter-empty]");
    var items = Array.prototype.slice.call(root.querySelectorAll("[data-filter-item]"));
    if (!items.length) return;

    var query = input ? (input.value || "").trim().toLowerCase() : "";
    var chip = root.querySelector("[data-filter-chip][aria-pressed='true']");
    var itemKey = chip ? chip.getAttribute("data-filter-chip") || "" : "";
    var shown = 0;

    items.forEach(function (el) {
      var hay = (el.getAttribute("data-search") || el.textContent || "").toLowerCase();
      var keys = (el.getAttribute("data-items") || "").split(/\s+/);
      var textOk = !query || hay.indexOf(query) !== -1;
      var chipOk = !itemKey || keys.indexOf(itemKey) !== -1;
      var match = textOk && chipOk;
      setHidden(el, !match);
      if (match) shown += 1;
    });

    if (status) {
      var noun = items.length === 1 ? "site" : "sites";
      if (!query && !itemKey) {
        status.textContent = "Showing " + shown + " " + noun + ".";
      } else {
        status.textContent = "Showing " + shown + " of " + items.length + " " + noun + ".";
      }
    }
    if (empty) empty.classList.toggle("is-visible", shown === 0);
  }

  function writeUrl(root) {
    if (root.getAttribute("data-filter-sync") === "off") return;
    var input = root.querySelector("[data-filter-input]");
    var chip = root.querySelector("[data-filter-chip][aria-pressed='true']");
    var url = new URL(window.location.href);
    var q = input ? input.value.trim() : "";
    var item = chip ? chip.getAttribute("data-filter-chip") || "" : "";
    if (q) url.searchParams.set("q", q);
    else url.searchParams.delete("q");
    if (item) url.searchParams.set("item", item);
    else url.searchParams.delete("item");
    if (window.history && window.history.replaceState) {
      window.history.replaceState({}, "", url);
    }
  }

  function bind(root) {
    var input = root.querySelector("[data-filter-input]");
    var chips = Array.prototype.slice.call(root.querySelectorAll("[data-filter-chip]"));
    var initial = params();

    if (input) {
      if (initial.get("q") && !input.value) input.value = initial.get("q");
      input.addEventListener("input", function () {
        apply(root);
        writeUrl(root);
      });
    }

    var wanted = initial.get("item") || "";
    chips.forEach(function (btn) {
      if (wanted && btn.getAttribute("data-filter-chip") === wanted) {
        btn.setAttribute("aria-pressed", "true");
      } else if (!btn.hasAttribute("aria-pressed")) {
        btn.setAttribute("aria-pressed", "false");
      }
      btn.addEventListener("click", function () {
        var on = btn.getAttribute("aria-pressed") === "true";
        chips.forEach(function (other) {
          other.setAttribute("aria-pressed", "false");
        });
        btn.setAttribute("aria-pressed", on ? "false" : "true");
        apply(root);
        writeUrl(root);
      });
    });

    var form = root.tagName === "FORM" ? root : root.querySelector("form");
    if (form) {
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        apply(root);
        writeUrl(root);
      });
    }

    apply(root);
  }

  document.querySelectorAll("[data-filter-root]").forEach(bind);
})();
