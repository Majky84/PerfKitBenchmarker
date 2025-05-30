"""Tests for managed_ai_model."""

import time
import unittest
from unittest import mock

from absl.testing import flagsaver
from absl.testing import parameterized
from perfkitbenchmarker import errors
from perfkitbenchmarker import sample
from tests import pkb_common_test_case
from tests.resources import fake_managed_ai_model

_ZONE = 'us-west-1a'


class ManagedAiModelTest(pkb_common_test_case.PkbCommonTestCase):

  def setUp(self):
    super().setUp()
    self.time_mock = self.enter_context(
        mock.patch.object(time, 'time', side_effect=range(100, 200))
    )
    self.enter_context(flagsaver.flagsaver(zone=[_ZONE]))

  def testUsesRegion(self):
    ai_model = fake_managed_ai_model.FakeManagedAiModel()
    self.assertEqual(ai_model.region, 'us-west-1a-region')

  def testThrowsRegionUnset(self):
    self.enter_context(flagsaver.flagsaver(zone=None))
    with self.assertRaises(errors.Setup.InvalidConfigurationError):
      fake_managed_ai_model.FakeManagedAiModel()

  def testSamplesAddedForSendingPrompt(self):
    ai_model = fake_managed_ai_model.FakeManagedAiModel()
    self.assertEmpty(ai_model.GetSamples())
    for i in range(1, 5):
      ai_model.SendPrompt('who?', 10, 1.0)
      self.assertLen(ai_model.GetSamples(), i)

  @parameterized.named_parameters(
      ('first_model', [], True),
      ('second_model', ['one-endpoint'], False),
  )
  def testCreateDepdenciesAddsMetadata(
      self, existing_endpoints, expected_metadata
  ):
    ai_model = fake_managed_ai_model.FakeManagedAiModel()
    ai_model._CreateDependencies()
    ai_model.existing_endpoints = existing_endpoints
    self.assertContainsSubset(
        {'First Model': expected_metadata}, ai_model.metadata
    )

  def testSampleTimedSendingPrompt(self):
    ai_model = fake_managed_ai_model.FakeManagedAiModel()
    ai_model.SendPrompt('who?', 10, 1.0)
    samples = ai_model.GetSamples()
    self.assertEqual(
        samples[0],
        sample.Sample(
            'response_time_0',
            1,
            'seconds',
            metadata={
                'interface': 'TEST',
                'region': 'us-west-1a-region',
                'max_scaling': 1,
                'resource_class': 'FakeManagedAiModel',
                'resource_type': 'BaseManagedAiModel',
            },
            timestamp=102,
        ),
    )


if __name__ == '__main__':
  unittest.main()
