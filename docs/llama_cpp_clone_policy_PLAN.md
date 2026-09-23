# 계획: ggml/llama.cpp 소스 클론 필요 여부 설명 절 (TODO 스텁)

> 상태: 기록용 스텁. 실제 대본/본문은 후속 커밋에서 작성된다.
> 완성 후 이 파일의 내용은 `docs/llama_cpp_provider.md` 에 "## 6. ggml/llama.cpp 소스 클론이 필요한 경우" 절로 병합되고, 이 임시 파일은 삭제된다.

## 배경

`llama_cpp` provider(`llama-cpp-python`)와 `llama_cpp_server` provider(`llama-server` 바이너리)가
각각 어떤 조건에서 ggml/llama.cpp 소스를 직접 클론해야 하는지를 명확히 해서,
사용자가 불필요한 빌드/툴체인 설치 단계를 밟지 않게 안내한다.

## 다룰 목록 (TODO)

- [ ] TODO: 사전 빌드 wheel 설치(기본 CPU 기준) 시 클론 불필요함을 명시
- [ ] TODO: CUDA/Metal/Vulkan 등 백엔드별 사전 빌드 wheel 지원 범위와 함께 정리
- [ ] TODO: 소스 빌드(`--no-binary`, `CMAKE_ARGS`) 시 pip가 서브모듈을 자동으로 당겨옴을 설명, 다만 로컬 툴체인(CMake/nvcc) 사전 설치 필요함을 적시
- [ ] TODO: `llama_cpp_server` provider용 `llama-server` 바이너리는 `llama-cpp-python`과 버전 범위가 다를 수 있음을 명시, 직접 `ggml-org/llama.cpp` 클론이 필요함을 명시
- [ ] TODO: 클론 필요 경우/불필요 경우를 하나의 비교 표로 정리

## 완성 기준

위 TODO 항목이 모두 해소되고, `docs/llama_cpp_provider.md`에 병합하는 커밋이 별도로 반영된다.
