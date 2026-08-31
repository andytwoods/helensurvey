/* Pathway Quiz — intro / statement / result flow.
 *
 * The browser collects ratings and renders the badge, but never decides the
 * outcome: it posts the raw ratings and the server returns the scored result.
 */
(function () {
  "use strict";

  var STATEMENTS = JSON.parse(document.getElementById("statements-data").textContent);
  var PATHWAYS = JSON.parse(document.getElementById("pathways-data").textContent);
  var SUBMIT_URL = document.getElementById("quizScript").dataset.submitUrl;
  var CSRF = document.querySelector("#csrfHolder [name=csrfmiddlewaretoken]").value;

  var META = {};
  PATHWAYS.forEach(function (p) { META[p.value] = p; });

  var order = [];
  var current = 0;
  var answers = [];
  var participantName = "";
  var submitting = false;

  var el = {
    intro: document.getElementById("intro"),
    nameInput: document.getElementById("nameInput"),
    startBtn: document.getElementById("startBtn"),
    progressFill: document.getElementById("progressFill"),
    qCount: document.getElementById("qCount"),
    qtext: document.getElementById("qtext"),
    backBtn: document.getElementById("backBtn"),
    badgeWrap: document.getElementById("badgeWrap"),
    resTitle: document.getElementById("resTitle"),
    resSubtitle: document.getElementById("resSubtitle"),
    resDesc: document.getElementById("resDesc"),
    toggleBreakdown: document.getElementById("toggleBreakdown"),
    breakdown: document.getElementById("breakdown"),
    breakdownRows: document.getElementById("breakdownRows"),
    saveStatus: document.getElementById("saveStatus"),
    retakeBtn: document.getElementById("retakeBtn")
  };

  function show(id) {
    document.querySelectorAll(".screen").forEach(function (s) {
      s.classList.remove("active");
    });
    document.getElementById(id).classList.add("active");
  }

  function shuffle(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = a[i];
      a[i] = a[j];
      a[j] = tmp;
    }
    return a;
  }

  function renderQuestion() {
    var item = order[current];
    el.qCount.textContent = "Statement " + (current + 1) + " / " + order.length;
    el.progressFill.style.width = (current / order.length) * 100 + "%";
    el.qtext.textContent = item.text;
    el.backBtn.style.visibility = current === 0 ? "hidden" : "visible";
  }

  function selectRating(rating) {
    answers[current] = rating;
    if (current < order.length - 1) {
      current++;
      renderQuestion();
    } else {
      submit();
    }
  }

  function svgNS(inner, attrs) {
    return "<svg viewBox=\"0 0 168 168\" xmlns=\"http://www.w3.org/2000/svg\">" + inner + "</svg>";
  }

  function buildBadge(result) {
    var primary = META[result.primary];
    var ascending = result.ascending ? META[result.ascending] : null;
    var isPure = result.is_pure || !ascending;
    var ringColor = isPure ? primary.hex : ascending.hex;
    var dash = isPure ? "" : " stroke-dasharray=\"4 5\"";
    var badgeIcon =
      "<g transform=\"translate(84,84) scale(2.15) translate(-12,-12)\" " +
      "style=\"stroke:#F6F3EC;stroke-width:1.7;fill:none;stroke-linecap:round;stroke-linejoin:round;\">" +
      primary.icon + "</g>";
    var ascendingMark = isPure ? "" :
      "<circle cx=\"138\" cy=\"132\" r=\"21\" fill=\"" + ascending.hex + "\" stroke=\"#17181C\" stroke-width=\"3\"/>" +
      "<g transform=\"translate(138,132) scale(0.85) translate(-12,-12)\" " +
      "style=\"stroke:#F6F3EC;stroke-width:2;fill:none;stroke-linecap:round;stroke-linejoin:round;\">" +
      ascending.icon + "</g>";

    return svgNS(
      "<circle cx=\"84\" cy=\"84\" r=\"80\" fill=\"none\" stroke=\"" + ringColor +
      "\" stroke-width=\"3\"" + dash + " opacity=\"" + (isPure ? 0.35 : 0.9) + "\"/>" +
      "<circle cx=\"84\" cy=\"84\" r=\"66\" fill=\"" + primary.hex + "\"/>" +
      badgeIcon + ascendingMark
    );
  }

  function buildHeart() {
    return svgNS(
      "<g transform=\"translate(84,84) scale(5.2) translate(-12,-12)\">" +
      "<path d=\"M12 21c-4.6-3-9-6.6-9-11.2C3 6.9 5.1 4.8 7.8 4.8c1.7 0 3.3.9 4.2 2.3.9-1.4 2.5-2.3 4.2-2.3 2.7 0 4.8 2.1 4.8 5 0 4.6-4.4 8.2-9 11.2z\" fill=\"#F3EFE6\"/>" +
      "</g>"
    );
  }

  function renderBreakdown(result) {
    var perPathway = result.statements_per_pathway || {};
    el.breakdownRows.innerHTML = PATHWAYS.map(function (p) {
      var total = perPathway[p.value] || 0;
      var confident = result.confident[p.value] || 0;
      var growing = result.growing[p.value] || 0;
      var confPct = total ? (confident / total) * 100 : 0;
      var growPct = total ? (growing / total) * 100 : 0;
      return (
        "<div class=\"brow\">" +
        "<div class=\"blabel\"></div>" +
        "<div class=\"btrack\">" +
        "<div class=\"bseg-confident\" style=\"width:" + confPct + "%;background:" + p.hex + "\"></div>" +
        "<div class=\"bseg-growing\" style=\"width:" + growPct + "%;background:" + p.hex + "\"></div>" +
        "</div>" +
        "<div class=\"bval\"></div>" +
        "</div>"
      );
    }).join("");
    // Labels and values are set as text, never interpolated into markup.
    var rows = el.breakdownRows.querySelectorAll(".brow");
    PATHWAYS.forEach(function (p, i) {
      rows[i].querySelector(".blabel").textContent = p.name;
      rows[i].querySelector(".bval").textContent =
        (result.confident[p.value] || 0) + "c · " + (result.growing[p.value] || 0) + "t";
    });
  }

  function renderResult(result) {
    if (result.all_skip) {
      el.badgeWrap.innerHTML = buildHeart();
      el.toggleBreakdown.style.display = "none";
      el.breakdown.classList.remove("open");
      el.breakdown.style.display = "none";
    } else {
      el.badgeWrap.innerHTML = buildBadge(result);
      el.toggleBreakdown.style.display = "";
      el.breakdown.style.display = "";
      renderBreakdown(result);
    }
    el.resTitle.textContent = result.title;
    el.resSubtitle.textContent = result.subtitle;
    el.resDesc.textContent = result.description;
    show("results");
  }

  function submit() {
    if (submitting) { return; }
    submitting = true;
    el.saveStatus.textContent = "Saving your result…";
    show("results");

    fetch(SUBMIT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": CSRF },
      body: JSON.stringify({
        name: participantName,
        answers: order.map(function (item, i) {
          return { statement: item.id, rating: answers[i] };
        })
      })
    })
      .then(function (res) {
        if (!res.ok) { throw new Error("Save failed: " + res.status); }
        return res.json();
      })
      .then(function (result) {
        renderResult(result);
        el.saveStatus.textContent = "Saved ✓";
      })
      .catch(function (err) {
        console.error(err);
        el.saveStatus.textContent = "Couldn't save your result — please try again.";
        el.resTitle.textContent = "Something went wrong.";
        el.resSubtitle.textContent = "";
        el.resDesc.textContent = "Your answers weren't saved. Tap “Take it again” to retry.";
      })
      .finally(function () {
        submitting = false;
      });
  }

  el.startBtn.addEventListener("click", function () {
    participantName = el.nameInput.value.trim();
    order = shuffle(STATEMENTS);
    current = 0;
    answers = new Array(order.length).fill(null);
    el.saveStatus.textContent = "";
    renderQuestion();
    show("quiz");
  });

  document.querySelectorAll("#rateWrap .rate-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      selectRating(btn.dataset.rating);
    });
  });

  el.backBtn.addEventListener("click", function () {
    if (current > 0) {
      current--;
      renderQuestion();
    }
  });

  el.toggleBreakdown.addEventListener("click", function () {
    var open = el.breakdown.classList.toggle("open");
    el.toggleBreakdown.textContent = open ? "Hide breakdown ↑" : "See your full breakdown ↓";
  });

  el.retakeBtn.addEventListener("click", function () {
    el.nameInput.value = participantName;
    show("intro");
  });
})();
