function displayRankings(endpoint, elementId, spinnerId) {
    // loading spinner
    document.getElementById(spinnerId).style.display = 'block';

    fetch(endpoint)
        .then(response => response.json())
        .then(data => {
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
            document.getElementById(spinnerId).style.display = 'none';
            console.error("Error fetching data:", error);
        });
}

function fetchGlobalRankings() {
    const numberOfTeams = document.getElementById('numberOfTeams').value;
    const dominance = document.getElementById('dominance').value;
    const consistency = document.getElementById('consistency').value;
    const regional_strength = document.getElementById('regional_strength').value;
    const streak_bonus = document.getElementById('streak_bonus').value;
    const streak_cutoff = document.getElementById('streak_cutoff').value;
    const underdog_bonus = document.getElementById('underdog_bonus').value;
    const int_underdog_cutoff = document.getElementById('int_underdog_cutoff').value;
    const reg_underdog_cutoff = document.getElementById('reg_underdog_cutoff').value;

    let endpoint = `https://k21eu7lqrd.execute-api.us-west-2.amazonaws.com/Beta/global-rankings?`;
    if (numberOfTeams) endpoint += `&number_of_teams=${numberOfTeams}`;
    if (dominance) endpoint += `&dominance=${dominance}`;
    if (consistency) endpoint += `&consistency=${consistency}`;
    if (regional_strength) endpoint += `&regional_strength=${regional_strength}`;
    if (streak_bonus) endpoint += `&streak_bonus=${streak_bonus}`;
    if (streak_cutoff) endpoint += `&streak_cutoff=${streak_cutoff}`;
    if (underdog_bonus) endpoint += `&underdog_bonus=${underdog_bonus}`;
    if (int_underdog_cutoff) endpoint += `&int_underdog_cutoff=${int_underdog_cutoff}`;
    if (reg_underdog_cutoff) endpoint += `&reg_underdog_cutoff=${reg_underdog_cutoff}`;

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

function fetchTeamRankings() {
    const teamIds = document.getElementById('teamIds').value;
    if (!teamIds) {
        alert("Please enter team IDs separated by commas.");
        return;
    }
    const endpoint = `https://k21eu7lqrd.execute-api.us-west-2.amazonaws.com/Beta/team-rankings?team_ids=${teamIds}`;
    displayRankings(endpoint, 'teamRankings', 'teamLoadingSpinner');
}

// fetch the global rankings on page load
fetchGlobalRankings();