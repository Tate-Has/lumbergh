Feature: Term and Conv views
  As a user I want the session rendered either as a raw terminal or as a
  readable conversation, without losing my session when I switch.

  Scenario: The toggle swaps between Term and Conv
    Given a test session exists
    And I am on the session page for "e2e-ui-session"
    Then I should see the terminal container
    When I click the view toggle
    Then I should see the conversation view
    And I should not see the terminal container

  Scenario: The view choice sticks across a reload
    Given a test session exists
    And I am on the session page for "e2e-ui-session"
    When I click the view toggle
    And I reload the page
    Then I should see the conversation view

  Scenario: Swapping back returns to a still-connected terminal
    Given a test session exists
    And I am on the session page for "e2e-ui-session"
    When I click the view toggle
    And I click the view toggle
    Then I should see the terminal container
    And the terminal is connected
