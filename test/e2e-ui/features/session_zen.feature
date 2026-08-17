Feature: Zen Mode
  As a user I want the terminal to fill the desktop viewport
  so I can watch a session without the side panel.

  Scenario: Alt+Z gives the terminal the whole viewport
    Given a test session exists
    And I am on the session page for "e2e-ui-session"
    Then I should see the git tab button
    When I press "Alt+z"
    Then I should not see the git tab button
    And I should see the terminal container

  Scenario: Alt+Z toggles back and leaves saved tabs alone
    Given a test session exists
    And I am on the session page for "e2e-ui-session"
    And I record the session's saved tab visibility
    When I press "Alt+z"
    And I press "Alt+z"
    And the network is idle
    Then I should see the git tab button
    And the session's saved tab visibility is unchanged
