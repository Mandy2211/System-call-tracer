cmake_minimum_required(VERSION 3.10)
project(syscall_tracer CXX)

# Use modern C++
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Output executables to bin/
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

# Add src files
file(GLOB SRC_FILES src/*.cpp)

add_executable(tracer ${SRC_FILES})

# pthread is often needed for timing / multithreading
find_package(Threads REQUIRED)
target_link_libraries(tracer PRIVATE Threads::Threads)

# Debug flags (use cmake -DCMAKE_BUILD_TYPE=Debug ..)
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    target_compile_options(tracer PRIVATE -Wall -Wextra -g)
endif()

