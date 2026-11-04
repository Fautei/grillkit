(function () {
    "use strict";

    var grammarCache = {};

    function initAnswerAssist() {
        var alertsHost = document.getElementById("interview-alerts");

        function showVoiceAlert(message, level) {
            if (!alertsHost) {
                return;
            }
            var alertDiv = document.createElement("div");
            alertDiv.className = "alert alert-" + (level || "warning");
            alertDiv.textContent = message;
            alertsHost.appendChild(alertDiv);
        }

        // ----- Grammar highlighting -------------------------------------

        function grammarUrl(interviewId, answerId) {
            return (
                "/interview/" +
                encodeURIComponent(interviewId) +
                "/theory/answer-grammar?answer_id=" +
                encodeURIComponent(String(answerId))
            );
        }

        function buildSegments(original, issues) {
            var ranges = [];
            var cursor = 0;
            (issues || []).forEach(function (issue) {
                var excerpt = issue.excerpt;
                if (!excerpt) {
                    return;
                }
                var idx = original.indexOf(excerpt, cursor);
                if (idx < 0) {
                    idx = original.indexOf(excerpt);
                }
                if (idx < 0) {
                    return;
                }
                var end = idx + excerpt.length;
                if (idx < cursor) {
                    return;
                }
                ranges.push({
                    start: idx,
                    end: end,
                    correction: issue.correction || "",
                    note: issue.note || "",
                });
                cursor = end;
            });
            ranges.sort(function (a, b) {
                return a.start - b.start;
            });

            var segments = [];
            var pos = 0;
            ranges.forEach(function (range) {
                if (range.start < pos) {
                    return;
                }
                if (range.start > pos) {
                    segments.push({
                        text: original.slice(pos, range.start),
                        incorrect: false,
                    });
                }
                segments.push({
                    text: original.slice(range.start, range.end),
                    incorrect: true,
                    correction: range.correction,
                    note: range.note,
                });
                pos = range.end;
            });
            if (pos < original.length) {
                segments.push({ text: original.slice(pos), incorrect: false });
            }
            return segments;
        }

        function renderHighlight(span, original, issues) {
            span.textContent = "";
            buildSegments(original, issues).forEach(function (segment) {
                var wrapper = document.createElement("span");
                wrapper.className =
                    "grammar-highlight " +
                    (segment.incorrect ? "incorrect" : "correct");
                wrapper.textContent = segment.text;
                if (segment.incorrect) {
                    var tip = document.createElement("span");
                    tip.className = "grammar-tooltip";
                    var label = segment.correction || "";
                    if (segment.note) {
                        label = label ? label + " — " + segment.note : segment.note;
                    }
                    tip.textContent = label;
                    wrapper.appendChild(tip);
                }
                span.appendChild(wrapper);
            });
        }

        function analyzeGrammar(interviewId, answerId) {
            if (grammarCache[answerId]) {
                return Promise.resolve(grammarCache[answerId]);
            }
            return fetch(grammarUrl(interviewId, answerId), { method: "POST" })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("grammar request failed");
                    }
                    return response.json();
                })
                .then(function (data) {
                    var result = {
                        corrected: data.corrected_answer || null,
                        issues: data.grammar_issues || [],
                    };
                    grammarCache[answerId] = result;
                    return result;
                });
        }

        function applyGrammarToSpan(span) {
            var interviewId = span.dataset.interviewId;
            var answerId = span.dataset.answerId;
            if (!interviewId || !answerId || span.dataset.grammarApplied === "true") {
                return;
            }
            span.dataset.grammarApplied = "true";
            var original = span.textContent;
            analyzeGrammar(interviewId, answerId)
                .then(function (result) {
                    if (result.issues && result.issues.length) {
                        renderHighlight(span, original, result.issues);
                    } else {
                        renderHighlight(span, original, []);
                    }
                })
                .catch(function () {
                    span.dataset.grammarApplied = "false";
                });
        }

        function observeAnswerSpans() {
            var spans = document.querySelectorAll(".answer-grammar");
            if (!spans.length) {
                return;
            }
            if (!("IntersectionObserver" in window)) {
                spans.forEach(applyGrammarToSpan);
                return;
            }
            var observer = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        applyGrammarToSpan(entry.target);
                        observer.unobserve(entry.target);
                    }
                });
            });
            spans.forEach(function (span) {
                if (span.dataset.grammarApplied !== "true") {
                    observer.observe(span);
                }
            });
        }

        // ----- Answer reference audio (plays corrected version) ---------

        var audioElement = null;
        var loadToken = 0;
        var activeButton = null;

        function setPlayingState(button, isPlaying) {
            document.querySelectorAll(".btn-answer-play").forEach(function (btn) {
                var active = isPlaying && btn === button;
                btn.classList.toggle("is-playing", active);
                btn.setAttribute("aria-pressed", active ? "true" : "false");
            });
        }

        function disposeAudio() {
            if (audioElement) {
                audioElement.pause();
                audioElement.removeAttribute("src");
                audioElement.load();
                audioElement = null;
            }
            setPlayingState(activeButton, false);
            activeButton = null;
        }

        function playBlob(button, blob) {
            var objectUrl = URL.createObjectURL(blob);
            audioElement = new Audio(objectUrl);
            audioElement.addEventListener("ended", function () {
                URL.revokeObjectURL(objectUrl);
                disposeAudio();
            });

            var startPlayback = function () {
                var playPromise = audioElement.play();
                if (!playPromise || typeof playPromise.then !== "function") {
                    setPlayingState(button, true);
                    return;
                }
                playPromise
                    .then(function () {
                        setPlayingState(button, true);
                    })
                    .catch(function () {
                        setPlayingState(button, false);
                        showVoiceAlert("Could not play answer audio.", "warning");
                    });
            };

            if (audioElement.readyState >= 2) {
                startPlayback();
            } else {
                audioElement.addEventListener("canplay", startPlayback, { once: true });
            }
            audioElement.load();
        }

        function fetchAudio(interviewId, answerId) {
            var url =
                "/interview/" +
                encodeURIComponent(interviewId) +
                "/answer-audio?answer_id=" +
                encodeURIComponent(String(answerId));
            return fetch(url, { method: "GET" }).then(function (response) {
                if (!response.ok) {
                    return response
                        .json()
                        .then(function (body) {
                            var detail = response.statusText;
                            if (body && body.detail) {
                                detail =
                                    typeof body.detail === "string"
                                        ? body.detail
                                        : String(body.detail);
                            }
                            throw new Error(detail);
                        })
                        .catch(function (err) {
                            if (err instanceof Error && err.message) {
                                throw err;
                            }
                            throw new Error(response.statusText || "Answer audio failed");
                        });
                }
                return response.blob();
            });
        }

        function playAnswerAudio(button) {
            var interviewId = button.dataset.interviewId;
            var answerId = button.dataset.answerId;
            if (!interviewId || !answerId) {
                return;
            }
            if (activeButton === button && audioElement) {
                disposeAudio();
                return;
            }

            var token = ++loadToken;
            disposeAudio();
            activeButton = button;
            button.classList.add("is-playing");

            // Ensure grammar analysis runs first so the corrected (reference)
            // version is persisted server-side for playback.
            analyzeGrammar(interviewId, answerId)
                .then(function () {
                    return fetchAudio(interviewId, answerId);
                })
                .then(function (blob) {
                    if (token !== loadToken) {
                        return;
                    }
                    playBlob(button, blob);
                })
                .catch(function (err) {
                    if (token !== loadToken) {
                        return;
                    }
                    disposeAudio();
                    showVoiceAlert(
                        err && err.message ? err.message : "Answer audio is unavailable.",
                        "warning"
                    );
                });
        }

        function bindAnswerPlayButtons(root) {
            var scope = root || document;
            scope.querySelectorAll(".btn-answer-play").forEach(function (button) {
                if (button.dataset.answerVoiceBound === "true") {
                    return;
                }
                button.dataset.answerVoiceBound = "true";
                button.addEventListener("click", function () {
                    playAnswerAudio(button);
                });
            });
        }

        window.grillkitBindAnswerPlayButtons = bindAnswerPlayButtons;

        bindAnswerPlayButtons(document);
        observeAnswerSpans();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initAnswerAssist);
    } else {
        initAnswerAssist();
    }
})();
