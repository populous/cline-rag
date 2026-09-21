# CMakeLists.txt -- cline_rag test pack
#
# Purpose: use CMake purely as a test-packing utility.
#   * no compilation happens (LANGUAGES NONE)
#   * an isolated test-venv is created and pytest installed into it
#   * pytest runs are registered as CTest tests (wrapping)
#
# Usage:
#   cmake -S . -B build
#   ctest --test-dir build -C Debug --output-on-failure
#   ctest --test-dir build -C Debug -L mcp      # only MCP tests
#   cmake --build build --config Debug --target test-pack
#
# Presets:
#   cmake --preset default
#   ctest --preset default

cmake_minimum_required(VERSION 3.20)

project(cline_rag LANGUAGES NONE)

include(CTest)

option(
    CLINE_RAG_SETUP_TEST_ENV
    "Create an isolated Python virtual environment and install test dependencies"
    ON
)

if(BUILD_TESTING)
    find_package(Python3 3.10 REQUIRED COMPONENTS Interpreter)

    set(CLINE_RAG_TEST_PYTHON "${Python3_EXECUTABLE}")

    # ------------------------------------------------------------------
    # Isolated test environment
    # ------------------------------------------------------------------
    if(CLINE_RAG_SETUP_TEST_ENV)
        set(CLINE_RAG_TEST_VENV "${CMAKE_BINARY_DIR}/test-venv")

        if(WIN32)
            set(CLINE_RAG_TEST_PYTHON "${CLINE_RAG_TEST_VENV}/Scripts/python.exe")
        else()
            set(CLINE_RAG_TEST_PYTHON "${CLINE_RAG_TEST_VENV}/bin/python")
        endif()

        if(NOT EXISTS "${CLINE_RAG_TEST_PYTHON}")
            message(STATUS "Creating isolated test environment: ${CLINE_RAG_TEST_VENV}")
            execute_process(
                COMMAND "${Python3_EXECUTABLE}" -m venv "${CLINE_RAG_TEST_VENV}"
                RESULT_VARIABLE venv_result
                ERROR_VARIABLE venv_error
            )
            if(NOT venv_result EQUAL 0)
                message(FATAL_ERROR "Failed to create the test environment: ${venv_error}")
            endif()
        endif()

        message(STATUS "Installing test dependencies (requirements.txt, requirements-dev.txt)")
        execute_process(
            COMMAND
                "${CLINE_RAG_TEST_PYTHON}" -m pip install
                --disable-pip-version-check --quiet
                -r "${CMAKE_SOURCE_DIR}/requirements.txt"
                -r "${CMAKE_SOURCE_DIR}/requirements-dev.txt"
            RESULT_VARIABLE pip_result
            ERROR_VARIABLE pip_error
        )
        if(NOT pip_result EQUAL 0)
            message(FATAL_ERROR "Failed to install test dependencies: ${pip_error}")
        endif()
    else()
        message(STATUS "Using existing Python interpreter: ${CLINE_RAG_TEST_PYTHON}")
    endif()

    # ------------------------------------------------------------------
    # pytest -> CTest wrapping
    # Tests are split by purpose and labelled so they can be run
    # selectively: ctest -L unit  /  ctest -L mcp
    # ------------------------------------------------------------------
    set(CLINE_RAG_TEST_ENV "PYTHONPATH=${CMAKE_SOURCE_DIR}/src")

    # 1) unit tests: chunking, cosine similarity, store CRUD, ranking
    add_test(
        NAME rag.unit
        COMMAND
            "${CLINE_RAG_TEST_PYTHON}" -m pytest
            "${CMAKE_SOURCE_DIR}/tests/test_rag_core.py"
            -v -p no:cacheprovider
        WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )

    set_tests_properties(
        rag.unit
        PROPERTIES
            LABELS "rag;unit"
            ENVIRONMENT "${CLINE_RAG_TEST_ENV}"
            TIMEOUT 1200
    )

    # 1b) hybrid retrieval: tokenisation, BM25, RRF, modes
    add_test(
        NAME rag.hybrid
        COMMAND
            "${CLINE_RAG_TEST_PYTHON}" -m pytest
            "${CMAKE_SOURCE_DIR}/tests/test_hybrid_search.py"
            -v -p no:cacheprovider
        WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )

    set_tests_properties(
        rag.hybrid
        PROPERTIES
            LABELS "rag;unit;hybrid"
            ENVIRONMENT "${CLINE_RAG_TEST_ENV}"
            TIMEOUT 1200
    )

    # 2) MCP protocol/tool tests
    add_test(
        NAME rag.mcp
        COMMAND
            "${CLINE_RAG_TEST_PYTHON}" -m pytest
            "${CMAKE_SOURCE_DIR}/tests/test_mcp_server.py"
            -v -p no:cacheprovider
        WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )

    set_tests_properties(
        rag.mcp
        PROPERTIES
            LABELS "rag;mcp;protocol"
            ENVIRONMENT "${CLINE_RAG_TEST_ENV}"
            TIMEOUT 1200
    )

    # 2b) ask.py CLI tests (no MCP/JSON-RPC involved, just argv -> stdout)
    add_test(
        NAME rag.cli
        COMMAND
            "${CLINE_RAG_TEST_PYTHON}" -m pytest
            "${CMAKE_SOURCE_DIR}/tests/test_ask_cli.py"
            -v -p no:cacheprovider
        WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )

    set_tests_properties(
        rag.cli
        PROPERTIES
            LABELS "rag;unit;cli"
            ENVIRONMENT "${CLINE_RAG_TEST_ENV}"
            TIMEOUT 1200
    )

    # 3) smoke test: spawn the server as a real child process (no pytest)
    add_test(
        NAME rag.smoke
        COMMAND "${CLINE_RAG_TEST_PYTHON}" "${CMAKE_SOURCE_DIR}/smoke_mcp.py"
        WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}"
    )

    set_tests_properties(
        rag.smoke
        PROPERTIES
            LABELS "rag;smoke"
            ENVIRONMENT "${CLINE_RAG_TEST_ENV}"
            TIMEOUT 300
    )

    message(STATUS "Registered CTest tests: rag.unit, rag.hybrid, rag.mcp, rag.cli, rag.smoke")

    # ------------------------------------------------------------------
    # Convenience target that runs the whole pack
    # ------------------------------------------------------------------
    add_custom_target(
        test-pack
        COMMAND
            "${CMAKE_CTEST_COMMAND}"
            --test-dir "${CMAKE_BINARY_DIR}"
            --build-config "$<CONFIG>"
            --output-on-failure
        COMMENT "Running the cline_rag test pack"
        USES_TERMINAL
    )
endif()