function displayRankings(endpoint, elementId, spinnerId) {
    // Show the spinner
    document.getElementById(spinnerId).style.display = 'block';

    fetch(endpoint)
        .then(response => response.json())
        .then(data => {
            // Hide the spinner
            document.getElementById(spinnerId).style.display = 'none';

            const rankingsDiv = document.getElementById(elementId);
            let rankingsHTML = '<ol>';
            for (let team of data) {
                rankingsHTML += `<li>${team.team_name} - Rank: ${team.rank}</li>`;
            }
            rankingsHTML += '</ol>';
            rankingsDiv.innerHTML = rankingsHTML;
        })
        .catch(error => {
            // Hide the spinner in case of an error
            document.getElementById(spinnerId).style.display = 'none';
            console.error("Error fetching data:", error);
        });
}

function fetchGlobalRankings() {
    const numberOfTeams = document.getElementById('numberOfTeams').value;
    const endpoint = `https://k21eu7lqrd.execute-api.us-west-2.amazonaws.com/Beta/global-rankings?number_of_teams=${numberOfTeams}`;
    displayRankings(endpoint, 'globalRankings', 'globalLoadingSpinner');
}

function fetchTournamentRankings() {
    const tournamentId = document.getElementById('tournamentDropdown').value; // Use 'tournamentDropdown' here
    const endpoint = `https://k21eu7lqrd.execute-api.us-west-2.amazonaws.com/Beta/tournament-rankings?tournament_id=${tournamentId}`;
    displayRankings(endpoint, 'tournamentRankings', 'tournamentLoadingSpinner');
}


const tournaments = [
    {id: "110848560874526298", name: "Season Finals 2023"},
    {id: "110535609415063567", name: "Summer 2023"},
    {id: "110847340080101648", name: "Playoffs - Summer 2023"},
    {id: "110825936250664572", name: "Regional Finals 2023"},
    {id: "110733838935136200", name: "#2 Summer 2023"},
    {id: "110423696147088301", name: "Summer 2023 - PCS"},
    {id: "110416959491275651", name: "Summer 2023 - VCS"},
    {id: "110507407705819578", name: "2023 - LJL Academy"},
    {id: "110428603624764603", name: "#1 Summer 2023"},
    {id: "110429332688604205", name: "Summer 2023 - LEC"}
];

function filterTournaments() {
    const query = document.getElementById('tournamentSearch').value.toLowerCase();
    const dropdown = document.getElementById('tournamentDropdown');

    // Clear existing options
    dropdown.innerHTML = '';

    // Filter and add matching tournaments to the dropdown
    for (let tournament of tournaments) {
        if (tournament.name.toLowerCase().includes(query)) {
            const option = document.createElement('option');
            option.value = tournament.id;
            option.textContent = tournament.name;
            dropdown.appendChild(option);
        }
    }
}
function fetchManualTournamentRankings() {
    const tournamentId = document.getElementById('manualTournamentId').value; 
    if (tournamentId.trim() === "") {
        alert("Please enter a tournament ID");
        return;
    }
    const endpoint = `https://k21eu7lqrd.execute-api.us-west-2.amazonaws.com/Beta/tournament-rankings?tournament_id=${tournamentId}`;
    displayRankings(endpoint, 'tournamentRankings', 'tournamentLoadingSpinner');
}



// Initial fetch for global rankings
fetchGlobalRankings();
