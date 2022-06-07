"use strict";

/// utility functions ///

function disableElement(el) {
    el.setAttribute("disabled", "disabled");
}

function enableElement(el) {
    el.removeAttribute("disabled");
}

function findParent(el, classList) {
    while (el !== null && !classList.every(cls => el.classList.contains(cls))) {
        el = el.parentNode;
    }

    return el;
}

function getFormData(form) {
    let formData = new FormData(form);
    let data = {};
    for (let key of formData.keys()) {
        let formType = form.getAttribute("data-form-type");
        if (formType === "CE")
            data[key] = formData.getAll(key);
        else
            data[key] = formData.get(key);
    }
    return data;
}

function setQuestionHighlight(questionCard, cardMode, buttonMode) {
    let submitButtons = questionCard.querySelectorAll("button.submit-button");
    setHighlightMode([questionCard], 'border', cardMode);
    setHighlightMode(submitButtons, 'btn', buttonMode);
}

function setHighlightMode(elements, prefix, mode) {

    let modes = ["info", "success", "danger"]

    elements.forEach(btn => {
        modes.forEach(m => {
            btn.classList.remove(`${prefix}-${m}`);
        });
        if (mode !== null)
            btn.classList.add(`${prefix}-${mode}`);
    })
}

/// dom manipulation ///

async function updatePollSummary(formContainer, pollResults) {
    let resultContainer = formContainer.querySelector(".poll-result");

    // Stop early if no results are shown
    if (resultContainer === null)
        return;

    let resultOptions = formContainer.querySelectorAll(".poll-result li");
    if (pollResults === null) {
        resultContainer.style.visibility = "hidden";
        return
    }

    resultContainer.style.visibility = "visible";
    resultContainer.querySelector(".total-vote-count").innerText = pollResults["totalVotes"]
    let pollIter = pollResults["options"].values();
    resultOptions.forEach(el => {
        let nextItem = pollIter.next();
        let {value: optionValue, count: optionCount} = nextItem.value;
        let optionPercentage = 0;

        if (pollResults["type"] === "Y3") {
            let optionCountDetails = optionCount;
            optionCount = optionCountDetails.reduce((a, b) => a + b);
            el.querySelector(".option-details").innerText = `Ja: ${optionCountDetails[0]}, `
                + `Nein: ${optionCountDetails[1]}, Enthaltung: ${optionCountDetails[2]}`;
            if (pollResults["totalVotes"] !== 0)
                optionPercentage = 100 * optionCountDetails[0] / pollResults["totalVotes"];
        }
        else if (pollResults["type"] === "PR")
            optionPercentage = 100 * optionCount / 5.0;
        else if (pollResults["totalVotes"] !== 0)
            optionPercentage = 100 * optionCount / pollResults["totalVotes"];

        el.querySelectorAll(".option-value").forEach((container) => {
            container.innerText = optionValue;
        })
        el.querySelectorAll(".option-vote-count").forEach((container) => {
            container.innerText = optionCount;
        })
        let progBar = el.querySelector(".progress-bar");
        if (pollResults["type"] === "PR")
            progBar.innerText = `${optionCount}/5.0`;
        else
            progBar.innerText = `${optionPercentage}%`;
        progBar.setAttribute("aria-valuenow", optionPercentage.toString());
        progBar.style.width = `${optionPercentage}%`;
    });
}

function showAlert(message, extraClasses) {
    let container = document.querySelector(".alerts-container");

    let alert = document.createElement("div");
    alert.classList.add("alert", "alert-dismissable", "fade", "show", ...extraClasses);
    alert.innerText = message;

    let btn = document.createElement("button");
    btn.classList.add("close");
    btn.setAttribute("data-dismiss", "alert");
    btn.setAttribute("aria-label", "close");
    btn.innerText = "x";

    alert.appendChild(btn);
    //container.appendChild(alert);
    container.insertBefore(alert, container.firstChild);
    $(alert).alert();
    setTimeout(() => {
        $(alert).alert('close');
    }, 10000);
}

function applyFilters() {

    console.log("filterIds: ", filterIds);

    updateUrlSearchParams();

    let filterWords = [].concat(tagFilters, filterQuery.split(" ")).filter(s => s.length !== 0);

    function shouldDisplayQuestion(q) {
        return (
            tagFilters.length === 0 || q.getAttribute("data-taglist")
                ?.split(" ")
                .some(tag => tagFilters.includes(tag))
        ) && (
            filterQuery.length === 0
            || filterWords.some(word => q.getAttribute("data-description")?.toLowerCase().indexOf(word.toLowerCase()) !== -1)
            || filterWords.some(word => q.getAttribute("data-question")?.toLowerCase().indexOf(word.toLowerCase()) !== -1)
        ) && (
            filterIds.length === 0
            || filterIds.includes(parseInt(q.getAttribute("data-id")))
        )
    }

    let questions = Array.from(document.querySelectorAll(".question-card"));
    let questionsToDisplay = questions
        .filter(q => shouldDisplayQuestion(q));
    let questionsToHide = questions
        .filter(q => !shouldDisplayQuestion(q));

    let filterButtons = Array.from(document.querySelectorAll(".tag-filter-button"));

    filterButtons
        .filter(btn => tagFilters.includes(btn.getAttribute("data-tag")))
        .forEach(btn => {
            btn.classList.remove("btn-secondary");
            btn.classList.add("btn-warning");
            btn.innerText = `${btn.getAttribute("data-tag")} (x)`
        })
    filterButtons
        .filter(btn => !tagFilters.includes(btn.getAttribute("data-tag")))
        .forEach(btn => {
            btn.classList.remove("btn-warning");
            btn.classList.add("btn-secondary");
            btn.innerText = `${btn.getAttribute("data-tag")}`
        })
    let clearFilterButton = document.querySelector(".clear-filter-button");

    if (filterWords.length === 0)
        clearFilterButton.style.display = "none";
    else
        clearFilterButton.style.removeProperty("display");
    console.log("filterWords: ", filterWords);

    questionsToDisplay
        .forEach(card => { card.style.removeProperty("display"); });
    questionsToHide
        .forEach(card => { card.style.display = "none"; });
}

/// api requests ///

async function submitForm(e) {
    e.preventDefault();

    let form = e.target;
    let questionCard = findParent(form, ['question-card']);
    let submitButtons = form.querySelectorAll("button.submit-button");

    let data = getFormData(form);
    let dataJson = JSON.stringify(data);

    submitButtons.forEach((btn) => {
        btn.setAttribute('data-text', btn.innerText);
        btn.innerText =". . .";
        btn.setAttribute("disabled", "disabled");
    });

    let responseData;
    let response;
    try {
        response = await fetch(form.action, {
            method: 'POST',
            mode: 'same-origin',
            cache: 'no-cache',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': data['csrfmiddlewaretoken']
            },
            redirect: 'follow',
            body: dataJson
        });
        responseData = await response.json();
    } catch (e) {
        responseData = null;
        console.warn("Did not receive a valid JSON response");
    }

    if (response.ok && responseData !== null) {
        let formId = form.getAttribute("data-form-id");
        await updatePollSummary(
            document.getElementById(`form-container-${formId}`),
            responseData["pollResults"]
        );
        console.log("Data submitted successfully.");
        showAlert(responseData?.message ?? "Deine Stimme wurde gespeichert.", ["alert-success"]);
        setQuestionHighlight(questionCard, 'success', 'success');
        let badgeContainer = questionCard.querySelector(".poll-badges");
        if (badgeContainer.querySelector(".success-badge") === null) {
            let successBadge = document.createElement("span");
            successBadge.classList.add("badge", "badge-info", "success-badge");
            successBadge.innerText = "Abgestimmt";
            badgeContainer.insertBefore(successBadge, badgeContainer.firstChild);
        }

        form.querySelectorAll("button.retract-button").forEach(enableElement);
    } else {
        console.warn(`Failed to submit data! Reason: ${responseData?.error ?? "unexpected error"}`);
        showAlert(`Beim Speichern deiner Stimme trat ein Fehler auf! `
            + `Grund: ${responseData?.error ?? "unexpected error"}`, ["alert-danger"]);
        setQuestionHighlight(questionCard, 'danger', 'danger');
    }

    submitButtons.forEach((btn) => {
        btn.innerText = btn.getAttribute('data-text');
        btn.removeAttribute("disabled");
    });

}

async function retractVote(e, form) {
    if (e.target.hasAttribute("disabled"))
        return;
    e.preventDefault();
    let data = getFormData(form);
    let responseData;
    let response;
    try {
        response = await fetch(form.action, {
            method: 'DELETE',
            mode: 'same-origin',
            cache: 'no-cache',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': data['csrfmiddlewaretoken']
            },
            redirect: 'follow',
        });
        responseData = await response.json();
    } catch (e) {
        responseData = null;
        console.warn("Did not receive a valid JSON response");
    }
    let questionCard = findParent(form, ['question-card']);

    if (response.ok && responseData !== null) {
        let formId = form.getAttribute("data-form-id");
        await updatePollSummary(
            document.getElementById(`form-container-${formId}`),
            responseData["pollResults"]
        );
        console.log("Data submitted successfully.");
        form.reset();
        showAlert(responseData?.message ?? "Deine Stimme wurde gelöscht.", ["alert-success"]);
        setQuestionHighlight(questionCard, null, 'info');
        form.querySelectorAll("button.retract-button").forEach(disableElement);
        let badge = questionCard.querySelector(".poll-badges .success-badge");
        badge?.parentNode.removeChild(badge);
    } else {
        console.warn(`Failed to submit data! Reason: ${responseData?.error ?? "unexpected error"}`);
        showAlert(`Beim Löschen deiner Stimme trat ein Fehler auf! `
            + `Grund: ${responseData?.error ?? "unexpected error"}`, ["alert-danger"]);
        setQuestionHighlight(questionCard, 'danger', 'danger');
    }
}

/// filter configuration ///

function toggleTagFilter(event, tag) {
    event.preventDefault();

    if (tagFilters.includes(tag))
        tagFilters.splice(tagFilters.indexOf(tag), 1);
    else
        tagFilters.push(tag);
    applyFilters();
}

function clearFilters(event) {
    event.preventDefault();

    if (tagFilters.length !== 0 || filterQuery.length > 0 || filterIds.length !== 0) {
        tagFilters = [];
        filterQuery = "";
        filterIds = [];
        document.querySelector(".search-form").reset();
        applyFilters();
    }
}

function updateUrlSearchParams() {

    let searchParams = new URLSearchParams(window.location.search);

    let tagParams = searchParams.getAll("tag");
    searchParams.delete("tag")
    tagFilters.forEach(tag => {
        if (!tagParams.includes(tag))
            searchParams.append("tag", tag);
    })

    if (filterQuery.length === 0)
        searchParams.delete("q")
    else
        searchParams.set("q", filterQuery);
    if (filterIds.length === 0)
        searchParams.delete("p")
    else
        filterIds.forEach(id => { searchParams.set("p", id); });

    if (searchParams !== window.location.searchParams) {
        let url = new URL(window.location.href);
        url.search = searchParams;
        window.history.pushState({}, "", url);
    }
}

/// ENTRYPOINT ///

let urlParams = new URLSearchParams(window.location.search);
let tagFilters = urlParams.getAll("tag");
let filterQuery = urlParams.get("q") ?? ""
let filterIds = urlParams.getAll("p")
    .map(s => {
        try {
            return parseInt(s)
        } catch (e) {
            showAlert("Ungültige ID in URL-Parameter 'p' (not a number)!", ["alert-warning"]);
            return null;
        }
    })
    .filter(i => i !== null);

document.querySelectorAll("form.poll-form").forEach((form) => {
    form.addEventListener("submit", submitForm);
});

document.querySelectorAll(".question-card").forEach(card => {
    let form = card.querySelector("form.poll-form");
    form.querySelectorAll("button.retract-button").forEach(btn => {
        if (card.querySelector(".poll-badges .success-badge") === null)
            btn.setAttribute("disabled", "disabled");
        btn.addEventListener("click", async e => { await retractVote(e, form); });
    })
})


document.querySelector(".clear-filter-button")
    .addEventListener("click", e => { clearFilters(e) });

document.querySelectorAll(".tag-filter-button").forEach(btn => {
    btn.addEventListener("click", e => { toggleTagFilter(e, btn.getAttribute("data-tag"))})
});

document.querySelector(".search-form").addEventListener("submit", (e) => {
    e.preventDefault();
    let data = new FormData(e.target);
    filterQuery = data.get("q");
    applyFilters();
});

if (filterQuery.length !== 0 || tagFilters.length !== 0 || filterIds.length !== 0)
    applyFilters();
