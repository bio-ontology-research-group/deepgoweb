# DeepGOWeb SPARQL endpoint — embedded Jena Fuseki (Jena 5, Java 21) exposing the
# dg:deepgo / dg:predict / dg:components property functions. Stateless: it serves an
# in-memory dataset and proxies prediction to the DeepGOWeb REST API (DEEPGO_API_BASE),
# so it needs no RDF data file.
FROM eclipse-temurin:21-jdk AS build
WORKDIR /src
COPY . /src
# installDist produces build/install/sparql/{bin,lib}
RUN ./gradlew --no-daemon installDist

FROM eclipse-temurin:21-jre
WORKDIR /opt/sparql
COPY --from=build /src/build/install/sparql/ /opt/sparql/
# DeepGOWeb API the property functions call (the `web` service in compose).
ENV DEEPGO_API_BASE=http://web:8000
EXPOSE 3330
# bin/sparql is the Gradle application launcher; --port sets the Fuseki port.
ENTRYPOINT ["/opt/sparql/bin/sparql"]
CMD ["--port", "3330"]
