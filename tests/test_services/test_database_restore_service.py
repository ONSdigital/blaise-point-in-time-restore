from unittest.mock import Mock, call

import pytest

from services.database_restore_service import DatabaseRestoreService


class TestRestoreFunctionality:
    @pytest.fixture()
    def mock_database_service(self):
        return Mock()

    @pytest.fixture()
    def service_under_test(self, mock_database_service: Mock) -> DatabaseRestoreService:
        return DatabaseRestoreService(
            database_service=mock_database_service,
            database_name="blaise",
        )

    def test_restores_dml_and_form_tables_for_blaise_database(
        self, mock_database_service, service_under_test
    ):
        # arrange
        table_name = "LMS2301_DD1"
        source_instance_name = "blaise-dev-test-clone"
        destination_instance_name = "blaise-dev-test"
        expected_calls = [
            call(
                f"{table_name}_Dml",
                source_instance_name,
                destination_instance_name,
            ),
            call(
                f"{table_name}_Form",
                source_instance_name,
                destination_instance_name,
            ),
        ]

        # act
        service_under_test.restore_table_data(
            table_name, source_instance_name, destination_instance_name
        )

        # assert
        mock_database_service.ensure_bucket_permissions_for_instances.assert_called_once_with(
            source_instance_name,
            destination_instance_name,
        )
        mock_database_service.copy_table_data.assert_has_calls(expected_calls)

    def test_restores_requested_table_for_non_blaise_database(
        self, mock_database_service
    ):
        table_name = "appointments"
        source_instance_name = "survey-dev-test-clone"
        destination_instance_name = "survey-dev-test"
        service_under_test = DatabaseRestoreService(
            database_service=mock_database_service,
            database_name="survey_data",
        )

        service_under_test.restore_table_data(
            table_name, source_instance_name, destination_instance_name
        )

        mock_database_service.ensure_bucket_permissions_for_instances.assert_called_once_with(
            source_instance_name,
            destination_instance_name,
        )
        mock_database_service.copy_table_data.assert_called_once_with(
            table_name,
            source_instance_name,
            destination_instance_name,
        )

    @pytest.mark.parametrize("table_name", [None, "", " ", "   "])
    def test_throws_error_when_no_table_name_is_provided(
        self, mock_database_service, service_under_test, table_name
    ):
        # arrange
        source_instance_name = "blaise-dev-test-clone"
        destination_instance_name = "blaise-dev-test"

        # act
        with pytest.raises(ValueError) as error:
            service_under_test.restore_table_data(
                table_name, source_instance_name, destination_instance_name
            )

        # assert
        assert str(error.value) == "table_name cannot be empty or none"

    @pytest.mark.parametrize("table_name", [None, "", " ", "   "])
    def test_does_not_call_database_service_when_no_table_name_provided(
        self, mock_database_service, service_under_test, table_name
    ):
        # arrange
        source_instance_name = "blaise-dev-test-clone"
        destination_instance_name = "blaise-dev-test"

        # act
        with pytest.raises(ValueError):
            service_under_test.restore_table_data(
                table_name, source_instance_name, destination_instance_name
            )

        # assert
        mock_database_service.ensure_bucket_permissions_for_instances.assert_not_called()
        mock_database_service.copy_table_data.assert_not_called()

    @pytest.mark.parametrize("source_instance_name", [None, "", " ", "   "])
    def test_throws_error_when_no_source_instance_is_provided(
        self, mock_database_service, service_under_test, source_instance_name
    ):
        # arrange
        table_name = "LMS2301_DD1"
        destination_instance_name = "blaise-dev-test"

        # act
        with pytest.raises(ValueError) as error:
            service_under_test.restore_table_data(
                table_name, source_instance_name, destination_instance_name
            )

        # assert
        assert str(error.value) == "source_instance_name cannot be empty or none"

    @pytest.mark.parametrize("source_instance_name", [None, "", " ", "   "])
    def test_does_not_call_database_service_when_no_source_instance_provided(
        self, mock_database_service, service_under_test, source_instance_name
    ):
        # arrange
        table_name = "LMS2301_DD1"
        destination_instance_name = "blaise-dev-test"

        # act
        with pytest.raises(ValueError):
            service_under_test.restore_table_data(
                table_name, source_instance_name, destination_instance_name
            )

        # assert
        mock_database_service.ensure_bucket_permissions_for_instances.assert_not_called()
        mock_database_service.copy_table_data.assert_not_called()

    @pytest.mark.parametrize("destination_instance_name", [None, "", " ", "   "])
    def test_throws_error_when_no_destination_instance_is_provided(
        self, mock_database_service, service_under_test, destination_instance_name
    ):
        # arrange
        table_name = "LMS2301_DD1"
        source_instance_name = "blaise-dev-test-clone"

        # act
        with pytest.raises(ValueError) as error:
            service_under_test.restore_table_data(
                table_name, source_instance_name, destination_instance_name
            )

        # assert
        assert str(error.value) == "destination_instance_name cannot be empty or none"

    @pytest.mark.parametrize("destination_instance_name", [None, "", " ", "   "])
    def test_does_not_call_database_service_when_no_destination_instance_provided(
        self, mock_database_service, service_under_test, destination_instance_name
    ):
        # arrange
        table_name = "LMS2301_DD1"
        source_instance_name = "blaise-dev-test-clone"

        # act
        with pytest.raises(ValueError):
            service_under_test.restore_table_data(
                table_name, source_instance_name, destination_instance_name
            )

        # assert
        mock_database_service.ensure_bucket_permissions_for_instances.assert_not_called()
        mock_database_service.copy_table_data.assert_not_called()
