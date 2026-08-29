Here is the blueprint for the roughly 30-minute continuous NEUROSCOPE module. The flow transitions from one task to the next without returning to a menu.

To ensure the $x_t = [S_t, A_t, R_t, \Delta t]$ sequence remains unbroken, Vansh can program the frontend to automatically chain these modules together without returning to a main menu, while Bhavya configures the database to tag every incoming row with the respective `task_id`.

### The NEUROSCOPE Master Sequence (Estimated Time: 30 Minutes)

---

### Module 0: Onboarding & Consent (0:00 - 0:03)

* **The Interface:** A clean, distraction-free screen displaying the IRB consent form approved by Ms. Anant and the board.
* **The Questions:**
* "Do you understand the risks and agree to participate?" (Requires a strict 'Yes' click).
* "What is your age?" (Dropdown: 13-17, 18-24, 25-34, etc.) -> Maps to `age_bracket`.
* "What is your highest level of education?" (Dropdown: High School, Bachelor's, etc.) -> Maps to `education_level`.


* **Database Trigger:** Generates the `participant_id` and logs the `session_start_timestamp`.

---

### Module 1: Probabilistic Learning (0:03 - 0:11)

* **Setup:** 60 rapid-fire trials. `task_id` = "prob_learning".
* **The Scenario (State Vector $S_t$):** Two distinct abstract symbols (e.g., a blue fractal and a red fractal) appear on screen.
* **The Question:** "Which symbol will give you a point?"
* **The Mechanic:**
* Trials 1–30: The blue symbol pays out 80% of the time (`prob_reward_a` = 0.8), and the red pays out 20% (`prob_reward_b` = 0.2).
* Trials 31–60: The probabilities silently flip. Blue is now 20%, red is 80%. On trial 31, `volatility_reversal` is flagged `true`.


* **Feedback ($R_t$):** A green "+1 Point" or a red "0 Points" appears immediately after the click.

---

### Module 2: Risk Preference (0:11 - 0:18)

* **Setup:** 30 trials. `task_id` = "risk_pref".
* **The Scenario (State Vector $S_t$):** A choice between a guaranteed safe harbor and a spinning wheel.
* **The Question:** "Choose your payout for this round:"
* Option A: "Guaranteed 50 Points"
* Option B: "A 50% chance to win 120 Points, and a 50% chance to win 0."


* **The Mechanic:** The `safe_amount` stays locked at 50. The `gamble_win_amount` and `gamble_probability` systematically vary. For example, the gamble might shift to a 20% chance to win 250 points, forcing the model to calculate their exact risk aversion curve.
* **Feedback ($R_t$):** If they choose the gamble, the wheel spins and resolves. If they choose safe, they instantly get the points.

---

### Module 3: Delay Discounting (0:18 - 0:25)

* **Setup:** 50 trials. `task_id` = "delay_disc".
* **The Scenario (State Vector $S_t$):** Two distinct time-locked vaults.
* **The Question:** "Would you rather have:"
* Option A: "100 Points right now."
* Option B: "150 Points in 7 days."


* **The Mechanic:** This task uses a titration method. If the user chooses the delayed option, the next trial makes the delayed option slightly less appealing (e.g., 150 points in 14 days). The `immediate_reward`, `delayed_reward`, and `delay_duration` variables constantly adjust based on their previous answers.
* **Feedback ($R_t$):** No immediate points are awarded; the choice is simply banked.

---

### Module 4: Different Patterns: Discover the Rule That Connects Them

* **Setup:** 60 trials. `task_id` = "rule_discovery".
* **The Scenario (State Vector $S_t$):** A target card appears in the center, with four base cards in the corners. Cards vary by Shape, Color, and Number of items.
* **The Question:** "Match the center card to one of the four corner cards. The matching rule is hidden."
* **The Mechanic:**
* Trials 1–15: The correct answer requires matching by **Color** (`current_rule_id` = "color").
* Trial 16: The rule silently shifts to **Shape**. The participant will likely get it wrong and must use trial-and-error to figure out the new logic. `rule_shift` is flagged `true`.


* **Feedback ($R_t$):** A simple "Correct" or "Incorrect" sound/visual.

---

### Module 5: Social Decision-Making (0:33 - 0:40)

* **Setup:** 40 trials. `task_id` = "social_ultimatum".
* **The Scenario (State Vector $S_t$):** An interactive prompt where the participant is paired with a "Partner" (an automated bot mimicking human behavior).
* **The Questions:**
* *When `trial_role` = "proposer":* "You have been given an `endowment` of 100 Points. How much do you offer your partner? (If they reject, you both get 0)." The user types in an `offer_amount`.
* *When `trial_role` = "responder":* "Your partner has 100 Points. They offered you 20 Points. Do you Accept or Reject?"


* **The Mechanic:** The bot is programmed to reject aggressively unfair offers (e.g., anything below 20). The participant alternates roles every 5 trials to see how rejection impacts their generosity.
* **Feedback ($R_t$):** "Offer Accepted! You keep 80, they get 20" or "Offer Rejected! You both get 0."

---

### System Architecture Note

Each click across the 240 trials logs the same core fields alongside `reaction_time_ms` ($\Delta t$), producing a consistent dataset for later analysis.

Are you planning to randomize the order of these five modules for each participant to prevent fatigue from skewing the results of the final task, or will you keep the task sequence identical for everyone?
