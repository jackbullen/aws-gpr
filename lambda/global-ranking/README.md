## Global Rankings Retrieval

The ranking process starts by executing a comprehensive SQL query against an Amazon Athena database. This query retrieves essential data, including:

1. Wins, losses, and ties for each team.
2. Regional and international statistics.
3. Team-specific details, like team ID and acronym.

With this data, we get a holistic view of each team's performance, both domestically and on the global stage.

## Innovative Metrics Calculation

Leveraging this data, we craft a series of metrics to evaluate each team's prowess:

1. **Total Games**:
$$\text{total}_{games} = \text{wins} + \text{losses}$$

2. **Win Percentage (Consistency)**:
$$\text{win}_{percentage} = \frac{\text{wins}}{\text{total}_{games}$$
This provides a direct measure of a team's success rate.

3. **Dominance**:
$$\text{dominance} = \text{wins} - \text{losses}$$
A measure that captures the net superiority of a team over its adversaries.

4. **Regional Strength**:
Derived from a team's performance in international matches compared to its regional counterparts.

5. **Streak Bonus**:
For teams that have consistently outperformed, having a win percentage above a set threshold (`streak_cutoff`), signifying their recent fiery form.

6. **Underdog Status**:
Teams that have shown resilience and potential despite not shining brightly on the international stage. Their international win percentages, when within a specific range, earn them the title of 'Underdogs' and a bonus to boot.

## Dynamic Ranking Logic

Using the metrics, we compute a weighted score for each team. The equation is:

$$\text{weighted}_{score} = \sum_{i=1}^{n} \text{metric}_i \times \text{weight}_i$$

Where:
- $ n $ is the total number of metrics.
- $ \text{metric}_i $ is the value of the $ i^{th} $ metric for a team.
- $ \text{weight}_i $ is the predetermined weight for the $ i^{th} $ metric, which can be adjusted based on user input.

Teams are then sorted in descending order based on their `weighted_score`. The higher the score, the higher they rank!

## The Grand Reveal

Our function concludes by presenting a list of the best teams in the world. By default, it showcases the top 10, but this number can be tailored to your preference. Each entry in the list provides the team's `team_id`, `team_name`, `acronym`, and their esteemed `rank`.
