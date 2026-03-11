Feature: Session Todos
  As a user I want to manage todos for my session.

  Scenario: Add a todo item
    Given I am on the session page for "e2e-ui-session"
    When I click the "todo" tab
    And I type "Buy more TPS reports" in the todo input
    And I press Enter in the todo input
    Then I should see a todo item with text "Buy more TPS reports"

  Scenario: Toggle a todo done
    Given I am on the session page for "e2e-ui-session"
    And a todo "Buy more TPS reports" exists
    When I click the "todo" tab
    And I toggle the checkbox for "Buy more TPS reports"
    Then the todo "Buy more TPS reports" should be marked done
