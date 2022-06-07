"use strict";

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

async function showAlert(message, extraClasses) {
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

function findParent(el, classList) {
    while (el !== null && !classList.every(cls => el.classList.contains(cls))) {
        el = el.parentNode;
    }

    return el;
}

async function submitForm(e) {
    e.preventDefault();
    let form = e.target;
    let formData = new FormData(form);
    let data = {};
    for (let key of formData.keys()) {
        let formType = form.getAttribute("data-form-type");
        if (formType === "CE")
            data[key] = formData.getAll(key);
        else
            data[key] = formData.get(key);
    }
    let dataJson = JSON.stringify(data);
    let submitButtons = form.querySelectorAll("button.submit-button");

    submitButtons.forEach((btn) => {
        btn.setAttribute('data-text', btn.innerText);
        btn.innerText =". . .";
        btn.setAttribute("disabled", "disabled");
    });

    let response = await fetch(form.action, {
        method: 'POST',
        mode: 'same-origin',
        cache: 'no-cache',
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': formData.get('csrfmiddlewaretoken')
        },
        redirect: 'follow',
        body: dataJson
    })
    let responseData;
    try {
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
        await showAlert(responseData?.message ?? "Deine Stimme wurde gespeichert.", ["alert-success"]);
        setHighlightMode([questionCard], 'border', 'success');
        setHighlightMode(submitButtons, 'btn', 'success');
        let badgeContainer = questionCard.querySelector(".poll-badges");
        if (badgeContainer.querySelector(".success-badge") === null) {
            let successBadge = document.createElement("span");
            successBadge.classList.add("badge", "badge-info", "success-badge");
            successBadge.innerText = "Abgestimmt";
            badgeContainer.insertBefore(successBadge, badgeContainer.firstChild);
        }

        form.querySelectorAll("button.retract-button").forEach(btn => {
            btn.removeAttribute("disabled");
        });
    } else {
        console.warn(`Failed to submit data! Reason: ${responseData?.error ?? "unexpected error"}`);
        await showAlert(`Beim Speichern deiner Stimme trat ein Fehler auf! `
            + `Grund: ${responseData?.error ?? "unexpected error"}`, ["alert-danger"]);
        setHighlightMode([questionCard], 'border', 'danger');
        setHighlightMode(submitButtons, 'btn', 'danger');
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
    let formData = new FormData(form);
    let response = await fetch(form.action, {
        method: 'DELETE',
        mode: 'same-origin',
        cache: 'no-cache',
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': formData.get('csrfmiddlewaretoken')
        },
        redirect: 'follow',
    })
    let responseData;
    try {
        responseData = await response.json();
    } catch (e) {
        responseData = null;
        console.warn("Did not receive a valid JSON response");
    }
    let questionCard = findParent(form, ['question-card']);
    let submitButtons = form.querySelectorAll("button.submit-button");
    let retractButtons = form.querySelectorAll("button.retract-button");

    if (response.ok && responseData !== null) {
        let formId = form.getAttribute("data-form-id");
        await updatePollSummary(
            document.getElementById(`form-container-${formId}`),
            responseData["pollResults"]
        );
        console.log("Data submitted successfully.");
        form.reset();
        await showAlert(responseData?.message ?? "Deine Stimme wurde gelöscht.", ["alert-success"]);
        setHighlightMode([questionCard], 'border', null);
        setHighlightMode(submitButtons, 'btn', 'info');
        retractButtons.forEach(btn => {
           btn.setAttribute("disabled", "disabled");
        });
        let badge = questionCard.querySelector(".poll-badges .success-badge");
        if (badge !== null) {
            badge.parentNode.removeChild(badge);
        }
    } else {
        console.warn(`Failed to submit data! Reason: ${responseData?.error ?? "unexpected error"}`);
        await showAlert(`Beim Löschen deiner Stimme trat ein Fehler auf! `
            + `Grund: ${responseData?.error ?? "unexpected error"}`, ["alert-danger"]);
        setHighlightMode([questionCard], 'border', 'danger');
        setHighlightMode(submitButtons, 'btn', 'danger');
    }
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
