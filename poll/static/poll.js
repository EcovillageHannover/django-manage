
async function updatePollSummary(formContainer, pollResults) {
    let resultContainer = formContainer.querySelector(".poll-result");
    let resultOptions = formContainer.querySelectorAll(".poll-result li");

    resultContainer.querySelector(".total-vote-count").innerText = pollResults["totalVotes"]
    let pollIter = pollResults["options"].values();
    resultOptions.forEach(el => {
        let nextItem = pollIter.next();
        let {value: optionValue, count: optionCount} = nextItem.value;
        let optionPercentage;

        if (pollResults["type"] === "Y3") {
            let optionCountDetails = optionCount;
            optionCount = optionCountDetails.reduce((a, b) => a + b);
            el.querySelector(".option-details").innerText = `Ja: ${optionCountDetails[0]}, `
                + `Nein: ${optionCountDetails[1]}, Enthaltung: ${optionCountDetails[2]}`;
            optionPercentage = 100 * optionCountDetails[0] / pollResults["totalVotes"];
        }
        else if (pollResults["type"] === "PR")
            optionPercentage = 100 * optionCount / 5.0;
        else
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
    pollResults["options"].forEach(({value: oValue, count: oCount}) => {

    })
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
    console.log("Form submitted:", dataJson);

    form.querySelectorAll("input[type=submit]").forEach((btn) => {
        btn.setAttribute('data-text', btn.getAttribute('value'));
        btn.setAttribute("value", "sending...");
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

    if (response.ok && responseData !== null) {
        console.log("Data submitted successfully.");
        let formId = form.getAttribute("data-form-id");
        await updatePollSummary(
            document.getElementById(`form-container-${formId}`),
            responseData["pollResults"]
        );
    } else {
        console.log("Failed to submit data:", responseData?.error ?? "unexpected error");
    }

    form.querySelectorAll("input[type=submit]").forEach((btn) => {
        btn.setAttribute('value', btn.getAttribute('data-text'));
    });

}

document.querySelectorAll("form.poll-form").forEach((form) => {
    form.addEventListener("submit", submitForm);
});
