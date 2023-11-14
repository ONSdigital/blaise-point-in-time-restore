import pytest

from unittest.mock import Mock, call

from services.database_restore_service import DatabaseRestoreService


@pytest.fixture()
def mock_database_service():
    return Mock()


@pytest.fixture()
def service_under_test(
        mock_database_service
) -> DatabaseRestoreService:
    return DatabaseRestoreService(
        database_service=mock_database_service,
    )


def test_database_restore_service_restores_a_list_of_questionnaires_data(
        mock_database_service,
        service_under_test
):
    # arrange
    questionnaire_names = ['LMS2301_DD1', 'LMS2301_EE1', 'LMS2301_FF1']
    source_instance_name = 'blaise-dev-test-clone'
    destination_instance_name = 'blaise-dev-test'
    expected_calls = [call(F'{questionnaire_names[0]}_DML', source_instance_name, destination_instance_name),
                      call(F'{questionnaire_names[0]}_FORM', source_instance_name, destination_instance_name),
                      call(F'{questionnaire_names[1]}_DML', source_instance_name, destination_instance_name),
                      call(F'{questionnaire_names[1]}_FORM', source_instance_name, destination_instance_name),
                      call(F'{questionnaire_names[2]}_DML', source_instance_name, destination_instance_name),
                      call(F'{questionnaire_names[2]}_FORM', source_instance_name, destination_instance_name)]

    # act
    service_under_test.restore_questionnaire_data(questionnaire_names, source_instance_name, destination_instance_name)

    # assert
    mock_database_service.copy_table_data.assert_has_calls(expected_calls)


@pytest.mark.parametrize("questionnaire_names", [[], None])
def test_database_restore_service_throws_an_error_when_no_questionnaires_are_provided(
        mock_database_service,
        service_under_test,
        questionnaire_names
):
    # arrange
    source_instance_name = 'blaise-dev-test-clone'
    destination_instance_name = 'blaise-dev-test'

    # act
    with pytest.raises(Exception) as error:
        service_under_test.restore_questionnaire_data(questionnaire_names, source_instance_name,
                                                      destination_instance_name)

    # assert
    assert str(error.value) == 'You must provide a Questionnaire name'


@pytest.mark.parametrize("questionnaire_names", [[], None])
def test_database_restore_service_does_not_call_database_service_when_no_questionnaires_are_provided(
        mock_database_service,
        service_under_test,
        questionnaire_names
):
    # arrange
    source_instance_name = 'blaise-dev-test-clone'
    destination_instance_name = 'blaise-dev-test'

    # act
    with pytest.raises(Exception):
        service_under_test.restore_questionnaire_data(questionnaire_names, source_instance_name,
                                                      destination_instance_name)

    # assert
    mock_database_service.copy_table_data.assert_not_called()


@pytest.mark.parametrize("source_instance_name", [None, '', ' ', '   '])
def test_database_restore_service_throws_an_error_when_no_source_instance_is_provided(
        mock_database_service,
        service_under_test,
        source_instance_name
):
    # arrange
    questionnaire_names = ['LMS2301_DD1']
    destination_instance_name = 'blaise-dev-test'

    # act
    with pytest.raises(Exception) as error:
        service_under_test.restore_questionnaire_data(questionnaire_names, source_instance_name,
                                                      destination_instance_name)

    # assert
    assert str(error.value) == 'You must provide a source instance name'


@pytest.mark.parametrize("source_instance_name", [None, '', ' ', '   '])
def test_database_restore_service_does_not_call_database_service_when_no_source_instance_is_provided(
        mock_database_service,
        service_under_test,
        source_instance_name
):
    # arrange
    questionnaire_names = ['LMS2301_DD1']
    destination_instance_name = 'blaise-dev-test'

    # act
    with pytest.raises(Exception):
        service_under_test.restore_questionnaire_data(questionnaire_names, source_instance_name,
                                                      destination_instance_name)

    # assert
    mock_database_service.copy_table_data.assert_not_called()


@pytest.mark.parametrize("destination_instance_name", [None, '', ' ', '   '])
def test_database_restore_service_throws_an_error_when_no_destination_instance_is_provided(
        mock_database_service,
        service_under_test,
        destination_instance_name
):
    # arrange
    questionnaire_names = ['LMS2301_DD1']
    source_instance_name = 'blaise-dev-test-clone'

    # act
    with pytest.raises(Exception) as error:
        service_under_test.restore_questionnaire_data(questionnaire_names, source_instance_name,
                                                      destination_instance_name)

    # assert
    assert str(error.value) == 'You must provide a destination instance name'


@pytest.mark.parametrize("destination_instance_name", [None, '', ' ', '   '])
def test_database_restore_service_does_not_call_database_service_when_no_destination_instance_is_provided(
        mock_database_service,
        service_under_test,
        destination_instance_name
):
    # arrange
    questionnaire_names = ['LMS2301_DD1']
    source_instance_name = 'blaise-dev-test-clone'

    # act
    with pytest.raises(Exception):
        service_under_test.restore_questionnaire_data(questionnaire_names, source_instance_name,
                                                      destination_instance_name)

    # assert
    mock_database_service.copy_table_data.assert_not_called()
