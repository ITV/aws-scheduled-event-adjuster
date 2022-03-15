# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from lib import utils
from lib.processors.base import ResourceProcessor

class EventBridgeProcessor(ResourceProcessor):
    def __init__(self, tag_prefix, eventbridge_service, recurrence_calculator):
        super().__init__(tag_prefix)
        self._eventbridge_service = eventbridge_service
        self._recurrence_calculator = recurrence_calculator

    def process_resources(self):
        changes = []

        rules = self._eventbridge_service.get_scheduled_rules()

        for rule in rules:
            try:
                print("Processing EventBridge rule '{}'".format(rule['Name']))

                tags = self._eventbridge_service.get_rule_tags(rule['Arn'])

                if utils.get_tag_by_key(tags, self._get_enabled_tag()) == None:
                    print("Skipping: EventBridge rule '{}' is not enabled (missing tag '{}')".format(rule['Name'],
                                                                                                     self._get_enabled_tag()))
                    continue

                local_timezone = utils.get_tag_by_key(tags, self._get_local_timezone_tag())
                local_time = utils.get_tag_by_key(tags, self._get_local_time_tag())
                local_to_time = utils.get_tag_by_key(tags, self._get_local_to_time_tag())

                if not local_timezone:
                    print("Skipping: EventBridge rule '{}' has no timezone defined (missing tag '{}')".format(rule['Name'],
                                                                                                              self._get_local_timezone_tag()))
                    continue

                if not local_time:
                    print("Skipping: EventBridge rule '{}' does not have local time tag (missing tag '{}')".format(rule['Name'],
                                                                                                                   self._get_local_time_tag()))
                    continue

                # Remove the 'cron()' surrounding the cron expression itself,
                # as the calculator does not expect it.
                # (This should probably be transparent to the caller, and the
                # calculator should handle it instead.)
                current_recurrence = rule['ScheduleExpression'][5:][:-1]

                if local_to_time:
                    new_recurrence = self._recurrence_calculator.calculate_range_recurrence(current_recurrence,
                                                                                            local_time,
                                                                                            local_to_time,
                                                                                            local_timezone)
                else:
                    new_recurrence = self._recurrence_calculator.calculate_recurrence(current_recurrence,
                                                                                      local_time,
                                                                                      local_timezone)
                if new_recurrence != current_recurrence:
                    print("Calculated recurrence '{}' does not match current recurrence '{}'. This rule will be updated.".format(new_recurrence, current_recurrence))
                    self._eventbridge_service.update_rule(rule,
                                                          'cron(' + new_recurrence + ')')
                    changes.append({
                        'Type': 'EventBridgeRule',
                        'ResourceName': rule['Name'],
                        'ResourceArn': rule['Arn'],
                        'OriginalRecurrence': current_recurrence,
                        'NewRecurrence': new_recurrence,
                        'LocalTime': local_time,
                        'LocalToTime': local_to_time,
                        'LocalTimezone': local_timezone
                    })

            except Exception as e:
                print("EventBridge rule failed to be processed: {}".format(str(e)))

        return changes
