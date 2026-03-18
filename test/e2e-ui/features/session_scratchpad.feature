Feature: Session Scratchpad
  As a user I want to write notes in the scratchpad for my session.

  Scenario: Write and read scratchpad content
    Given I am on the session page for "e2e-ui-session"
    When I click the "todo" tab
    And I type "# E2E Test Notes" in the scratchpad
    Then the scratchpad should contain "# E2E Test Notes"

  Scenario: Scratchpad content is isolated between sessions
    Given I am on the session page for "e2e-ui-session"
    And a second test session exists
    When I click the "todo" tab
    And I type "Notes for session 1" in the scratchpad
    And I navigate to the session page for "e2e-ui-session-2"
    And I click the "todo" tab
    Then the scratchpad should not contain "Notes for session 1"
